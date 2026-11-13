package com.coride.app

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import java.net.Inet4Address

class MainActivity : Activity() {
    private lateinit var nsdManager: NsdManager
    private lateinit var loaderScreen: FrameLayout
    private lateinit var loaderWebView: WebView
    private lateinit var loadingStatus: TextView
    private lateinit var offlineScreen: LinearLayout
    private lateinit var retryButton: Button
    private lateinit var webView: WebView
    private val mainHandler = Handler(Looper.getMainLooper())
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var discoveryTimeout: Runnable? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var discoveryGeneration = 0
    private var resolvingService = false
    private var fallbackAttempted = false
    private var loadingFallback = false
    private var currentServerHost: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        nsdManager = getSystemService(Context.NSD_SERVICE) as NsdManager

        val density = resources.displayMetrics.density
        val padding = (16 * density).toInt()
        loadingStatus = TextView(this).apply {
            gravity = Gravity.CENTER
            setPadding(padding, padding, padding, padding)
            text = getString(R.string.searching_for_server)
            textSize = 16f
            setTextColor(Color.rgb(96, 119, 138))
        }
        loaderWebView = WebView(this).apply {
            settings.javaScriptEnabled = false
            settings.allowFileAccess = false
            settings.blockNetworkLoads = true
            webViewClient = WebViewClient()
        }
        val loaderHtml = assets.open("coride-loader.html").bufferedReader().use { it.readText() }
        loaderWebView.loadDataWithBaseURL(
            "https://appassets.androidplatform.net/",
            loaderHtml,
            "text/html",
            "UTF-8",
            null,
        )
        loaderScreen = FrameLayout(this).apply {
            addView(
                loaderWebView,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
            addView(
                loadingStatus,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                    Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL,
                ).apply {
                    bottomMargin = (48 * density).toInt()
                },
            )
        }
        retryButton = Button(this).apply {
            text = getString(R.string.retry_discovery)
            setOnClickListener { startDiscovery() }
        }
        val appTitle = TextView(this).apply {
            text = getString(R.string.app_name)
            textSize = 34f
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
            setTextColor(Color.rgb(23, 47, 70))
        }
        val offlineLogo = ImageView(this).apply {
            setImageResource(R.drawable.kitty)
            contentDescription = getString(R.string.app_name)
            scaleType = ImageView.ScaleType.FIT_CENTER
        }
        val offlineMessage = TextView(this).apply {
            gravity = Gravity.CENTER
            setPadding(padding, padding, padding, padding)
            text = getString(R.string.server_offline)
            textSize = 16f
            setTextColor(Color.rgb(96, 119, 138))
        }
        offlineScreen = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(padding, padding, padding, padding)
            setBackgroundColor(Color.rgb(242, 247, 246))
            addView(
                offlineLogo,
                LinearLayout.LayoutParams(
                    (180 * density).toInt(),
                    (180 * density).toInt(),
                ),
            )
            addView(
                appTitle,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply {
                    topMargin = (20 * density).toInt()
                },
            )
            addView(
                offlineMessage,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply {
                    topMargin = (8 * density).toInt()
                },
            )
            addView(
                retryButton,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply {
                    topMargin = (12 * density).toInt()
                },
            )
            visibility = View.GONE
        }
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            visibility = View.GONE
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(
                    view: WebView?,
                    request: WebResourceRequest?,
                ): Boolean {
                    val scheme = request?.url?.scheme
                    return scheme != "http" && scheme != "https"
                }

                override fun onPageStarted(
                    view: WebView?,
                    url: String?,
                    favicon: android.graphics.Bitmap?,
                ) {
                    showLoading(
                        getString(
                            if (loadingFallback) {
                                R.string.loading_online_server
                            } else {
                                R.string.connecting_to_server
                            },
                        ),
                    )
                }

                override fun onPageFinished(view: WebView?, url: String?) {
                    if (!isCurrentServerUrl(url)) return
                    webView.visibility = View.VISIBLE
                    loaderScreen.visibility = View.GONE
                    offlineScreen.visibility = View.GONE
                }

                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: android.webkit.WebResourceError?,
                ) {
                    if (isCurrentMainFrameRequest(request)) {
                        Log.w(TAG, "CoRide page failed to load: ${error?.errorCode}")
                        handleServerUnavailable()
                    }
                }

                override fun onReceivedHttpError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    errorResponse: android.webkit.WebResourceResponse?,
                ) {
                    if (
                        isCurrentMainFrameRequest(request) &&
                        errorResponse != null &&
                        errorResponse.statusCode >= 400
                    ) {
                        Log.w(TAG, "CoRide returned HTTP ${errorResponse.statusCode}")
                        handleServerUnavailable()
                    }
                }
            }
        }

        val root = FrameLayout(this).apply {
            addView(
                webView,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
            addView(
                loaderScreen,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
            addView(
                offlineScreen,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
        }
        setContentView(root)

        if (BuildConfig.SERVER_URL.isNotBlank()) {
            loadServer(BuildConfig.SERVER_URL)
        } else {
            startDiscovery()
        }
    }

    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        discoveryGeneration++
        stopDiscovery()
        loaderWebView.destroy()
        webView.destroy()
        super.onDestroy()
    }

    private fun startDiscovery() {
        stopDiscovery()
        val generation = ++discoveryGeneration
        resolvingService = false
        fallbackAttempted = false
        loadingFallback = false
        webView.stopLoading()
        webView.visibility = View.GONE
        showLoading(getString(R.string.searching_for_server))

        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        multicastLock = wifiManager.createMulticastLock("CoRide discovery").apply {
            setReferenceCounted(false)
            acquire()
        }

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) = Unit

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                mainHandler.post {
                    if (
                        generation != discoveryGeneration ||
                        resolvingService ||
                        !serviceInfo.serviceType.startsWith(SERVICE_TYPE)
                    ) {
                        return@post
                    }
                    resolvingService = true
                    loadingStatus.text = getString(R.string.connecting_to_server)
                    nsdManager.resolveService(
                        serviceInfo,
                        object : NsdManager.ResolveListener {
                            override fun onServiceResolved(resolvedInfo: NsdServiceInfo) {
                                mainHandler.post {
                                    if (generation != discoveryGeneration) return@post
                                    val host = resolvedInfo.host
                                    if (
                                        host !is Inet4Address ||
                                        !host.isSiteLocalAddress ||
                                        host.isLoopbackAddress ||
                                        host.isLinkLocalAddress ||
                                        host.isAnyLocalAddress ||
                                        host.isMulticastAddress
                                    ) {
                                        fallbackToHostedServer()
                                        return@post
                                    }

                                    stopDiscovery()
                                    loadServer("http://${host.hostAddress}:${resolvedInfo.port}")
                                }
                            }

                            override fun onResolveFailed(
                                failedServiceInfo: NsdServiceInfo,
                                errorCode: Int,
                            ) {
                                Log.w(TAG, "Could not resolve CoRide service: $errorCode")
                                mainHandler.post {
                                    if (generation == discoveryGeneration) {
                                        resolvingService = false
                                        loadingStatus.text = getString(R.string.searching_for_server)
                                    }
                                }
                            }
                        },
                    )
                }
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) = Unit

            override fun onDiscoveryStopped(serviceType: String) = Unit

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "CoRide discovery failed to start: $errorCode")
                mainHandler.post {
                    if (generation == discoveryGeneration) {
                        discoveryListener = null
                        cancelDiscoveryTimeout()
                        releaseMulticastLock()
                        fallbackToHostedServer()
                    }
                }
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "CoRide discovery failed to stop: $errorCode")
            }
        }
        discoveryListener = listener

        try {
            nsdManager.discoverServices(
                SERVICE_TYPE,
                NsdManager.PROTOCOL_DNS_SD,
                listener,
            )
        } catch (error: IllegalArgumentException) {
            Log.e(TAG, "Invalid CoRide discovery service type", error)
            discoveryListener = null
            releaseMulticastLock()
            fallbackToHostedServer()
            return
        } catch (error: SecurityException) {
            Log.e(TAG, "Permission denied while discovering CoRide", error)
            discoveryListener = null
            releaseMulticastLock()
            fallbackToHostedServer()
            return
        }

        val timeout = Runnable {
            if (generation == discoveryGeneration && discoveryListener != null) {
                stopDiscovery()
                fallbackToHostedServer()
            }
        }
        discoveryTimeout = timeout
        mainHandler.postDelayed(timeout, DISCOVERY_TIMEOUT_MS)
    }

    private fun stopDiscovery() {
        val listener = discoveryListener
        discoveryListener = null
        cancelDiscoveryTimeout()
        if (listener != null) {
            try {
                nsdManager.stopServiceDiscovery(listener)
            } catch (error: IllegalArgumentException) {
                Log.w(TAG, "CoRide service discovery was already stopped", error)
            }
        }
        releaseMulticastLock()
    }

    private fun cancelDiscoveryTimeout() {
        discoveryTimeout?.let(mainHandler::removeCallbacks)
        discoveryTimeout = null
    }

    private fun releaseMulticastLock() {
        multicastLock?.let { lock ->
            if (lock.isHeld) lock.release()
        }
        multicastLock = null
    }

    private fun loadServer(url: String) {
        loadServer(url, isFallback = false)
    }

    private fun loadServer(url: String, isFallback: Boolean) {
        loadingFallback = isFallback
        currentServerHost = Uri.parse(url).host
        showLoading(
            getString(
                if (isFallback) {
                    R.string.loading_online_server
                } else {
                    R.string.connecting_to_server
                },
            ),
        )
        webView.loadUrl(url)
    }

    private fun isCurrentMainFrameRequest(request: WebResourceRequest?): Boolean {
        return request?.isForMainFrame == true &&
            request.url.host.equals(currentServerHost, ignoreCase = true)
    }

    private fun isCurrentServerUrl(url: String?): Boolean {
        return url != null &&
            Uri.parse(url).host.equals(currentServerHost, ignoreCase = true)
    }

    private fun showLoading(message: String) {
        loadingStatus.text = message
        loaderScreen.visibility = View.VISIBLE
        offlineScreen.visibility = View.GONE
        webView.visibility = View.GONE
    }

    private fun fallbackToHostedServer() {
        if (fallbackAttempted) {
            showOfflinePage()
            return
        }
        fallbackAttempted = true
        discoveryGeneration++
        stopDiscovery()
        loadServer(FALLBACK_URL, isFallback = true)
    }

    private fun handleServerUnavailable() {
        if (loadingFallback) {
            showOfflinePage()
        } else {
            fallbackToHostedServer()
        }
    }

    private fun showOfflinePage() {
        webView.stopLoading()
        webView.visibility = View.GONE
        loaderScreen.visibility = View.GONE
        offlineScreen.visibility = View.VISIBLE
    }

    private companion object {
        const val SERVICE_TYPE = "_coride._tcp."
        const val DISCOVERY_TIMEOUT_MS = 15_000L
        const val FALLBACK_URL = "https://coride-sep.vercel.app/"
        const val TAG = "CoRide"
    }
}
