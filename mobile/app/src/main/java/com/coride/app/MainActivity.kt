package com.coride.app

import android.app.Activity
import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.net.Inet4Address

class MainActivity : Activity() {
    private lateinit var nsdManager: NsdManager
    private lateinit var status: TextView
    private lateinit var retryButton: Button
    private lateinit var webView: WebView
    private val mainHandler = Handler(Looper.getMainLooper())
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var discoveryTimeout: Runnable? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var discoveryGeneration = 0
    private var resolvingService = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        nsdManager = getSystemService(Context.NSD_SERVICE) as NsdManager

        val padding = (16 * resources.displayMetrics.density).toInt()
        status = TextView(this).apply {
            gravity = Gravity.CENTER
            setPadding(padding, padding, padding, padding)
            text = getString(R.string.searching_for_server)
        }
        retryButton = Button(this).apply {
            text = getString(R.string.retry_discovery)
            visibility = View.GONE
            setOnClickListener { startDiscovery() }
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
                    status.text = getString(R.string.connecting_to_server)
                    status.visibility = View.VISIBLE
                }

                override fun onPageFinished(view: WebView?, url: String?) {
                    status.visibility = View.GONE
                }

                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: android.webkit.WebResourceError?,
                ) {
                    if (request?.isForMainFrame == true) {
                        showConnectionFailure()
                    }
                }
            }
        }

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(
                status,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ),
            )
            addView(
                retryButton,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ),
            )
            addView(
                webView,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    0,
                    1f,
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
        webView.destroy()
        super.onDestroy()
    }

    private fun startDiscovery() {
        stopDiscovery()
        val generation = ++discoveryGeneration
        resolvingService = false
        webView.visibility = View.GONE
        retryButton.visibility = View.GONE
        status.text = getString(R.string.searching_for_server)
        status.visibility = View.VISIBLE

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
                    status.text = getString(R.string.connecting_to_server)
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
                                        showDiscoveryFailure()
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
                                        status.text = getString(R.string.searching_for_server)
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
                        showDiscoveryFailure()
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
            showDiscoveryFailure()
            return
        } catch (error: SecurityException) {
            Log.e(TAG, "Permission denied while discovering CoRide", error)
            discoveryListener = null
            releaseMulticastLock()
            showDiscoveryFailure()
            return
        }

        val timeout = Runnable {
            if (generation == discoveryGeneration && discoveryListener != null) {
                discoveryGeneration++
                stopDiscovery()
                showDiscoveryFailure()
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
        status.text = getString(R.string.connecting_to_server)
        status.visibility = View.VISIBLE
        retryButton.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl(url)
    }

    private fun showDiscoveryFailure() {
        status.text = getString(R.string.server_not_found)
        status.visibility = View.VISIBLE
        retryButton.visibility = View.VISIBLE
        webView.visibility = View.GONE
    }

    private fun showConnectionFailure() {
        status.text = getString(R.string.connection_failed)
        status.visibility = View.VISIBLE
        retryButton.visibility = View.VISIBLE
        webView.visibility = View.GONE
    }

    private companion object {
        const val SERVICE_TYPE = "_coride._tcp."
        const val DISCOVERY_TIMEOUT_MS = 15_000L
        const val TAG = "CoRide"
    }
}
