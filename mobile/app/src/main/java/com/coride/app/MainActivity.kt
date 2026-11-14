package com.coride.app

import android.app.Activity
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.io.FileInputStream
import java.io.IOException
import java.net.Inet4Address
import org.json.JSONObject

class MainActivity : Activity() {
    private lateinit var nsdManager: NsdManager
    private lateinit var loaderScreen: FrameLayout
    private lateinit var loaderWebView: WebView
    private lateinit var loadingStatus: TextView
    private lateinit var versionLabel: TextView
    private lateinit var offlineScreen: LinearLayout
    private lateinit var retryButton: Button
    private lateinit var webView: WebView
    private lateinit var navigationBar: LinearLayout
    private lateinit var navigationDrawer: LinearLayout
    private lateinit var navigationScrim: View
    private lateinit var currentPathLabel: TextView
    private val mainHandler = Handler(Looper.getMainLooper())
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var discoveryTimeout: Runnable? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var discoveryGeneration = 0
    private var resolvingService = false
    private var fallbackAttempted = false
    private var loadingFallback = false
    private var currentServerHost: String? = null
    private var currentServerOrigin: String? = null
    private var updateCheckInProgress = false
    private var updateDownloadInProgress = false
    private var pendingUpdate: PendingUpdate? = null
    private var rejectedUpdateVersion: String? = null
    private val releaseUpdater by lazy { GitHubReleaseUpdater(applicationContext) }
    private val updateCheckTask = object : Runnable {
        override fun run() {
            checkForUpdates()
            mainHandler.postDelayed(this, UPDATE_CHECK_INTERVAL_MS)
        }
    }

    private data class PendingUpdate(val apk: File, val versionName: String)
    private data class NavigationDestination(val titleRes: Int, val path: String)

    private val navigationDestinations = listOf(
        NavigationDestination(R.string.navigation_home, "/"),
        NavigationDestination(R.string.navigation_users, "/users/"),
        NavigationDestination(R.string.navigation_vehicles, "/vehicles/"),
        NavigationDestination(R.string.navigation_trips, "/trips/"),
        NavigationDestination(R.string.navigation_reservations, "/reservations/"),
        NavigationDestination(R.string.navigation_communication, "/coms/"),
    )

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
            setTextColor(getColor(R.color.app_secondary_text))
        }
        versionLabel = TextView(this).apply {
            gravity = Gravity.CENTER
            text = getString(R.string.app_version, BuildConfig.VERSION_NAME)
            textSize = 12f
            setTextColor(getColor(R.color.app_secondary_text))
        }
        val loadingFooter = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            addView(
                loadingStatus,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                ),
            )
            addView(
                versionLabel,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                ),
            )
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
                loadingFooter,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                    Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL,
                ).apply {
                    bottomMargin = (32 * density).toInt()
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
            setTextColor(getColor(R.color.app_heading))
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
            setTextColor(getColor(R.color.app_secondary_text))
        }
        offlineScreen = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(padding, padding, padding, padding)
            setBackgroundColor(getColor(R.color.app_surface))
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
                    updateCurrentPath(url)
                    applySystemThemeToPage {
                        if (webView.url != url) return@applySystemThemeToPage
                        webView.visibility = View.VISIBLE
                        loaderScreen.visibility = View.GONE
                        offlineScreen.visibility = View.GONE
                        navigationBar.visibility = View.VISIBLE
                    }
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

        navigationBar = createNavigationBar(density)
        navigationScrim = View(this).apply {
            setBackgroundColor(Color.BLACK)
            alpha = 0.45f
            visibility = View.GONE
            setOnClickListener { closeNavigationDrawer() }
        }
        navigationDrawer = createNavigationDrawer(density).apply {
            visibility = View.GONE
        }
        val navigationBarHeight = (56 * density).toInt()
        val root = FrameLayout(this).apply {
            setBackgroundColor(getColor(R.color.app_surface))
            addView(
                webView,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ).apply {
                    topMargin = navigationBarHeight
                },
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
            addView(
                navigationBar,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    navigationBarHeight,
                    Gravity.TOP,
                ),
            )
            addView(
                navigationScrim,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
            addView(
                navigationDrawer,
                FrameLayout.LayoutParams(
                    minOf(
                        (320 * density).toInt(),
                        (resources.displayMetrics.widthPixels * 0.85f).toInt(),
                    ),
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    Gravity.START,
                ),
            )
        }
        root.setOnApplyWindowInsetsListener { _, insets ->
            val statusBarInset = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                insets.getInsets(WindowInsets.Type.statusBars()).top
            } else {
                @Suppress("DEPRECATION")
                insets.systemWindowInsetTop
            }
            (webView.layoutParams as FrameLayout.LayoutParams).apply {
                topMargin = statusBarInset + navigationBarHeight
            }.also { webView.layoutParams = it }
            (navigationBar.layoutParams as FrameLayout.LayoutParams).apply {
                topMargin = statusBarInset
            }.also { navigationBar.layoutParams = it }
            (navigationDrawer.layoutParams as FrameLayout.LayoutParams).apply {
                topMargin = statusBarInset
            }.also { navigationDrawer.layoutParams = it }
            insets
        }
        setContentView(root)

        if (BuildConfig.SERVER_URL.isNotBlank()) {
            loadServer(BuildConfig.SERVER_URL)
        } else {
            startDiscovery()
        }
        checkForUpdates()
        mainHandler.postDelayed(updateCheckTask, UPDATE_CHECK_INTERVAL_MS)
    }

    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (navigationDrawer.visibility == View.VISIBLE) {
            closeNavigationDrawer()
        } else if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onResume() {
        super.onResume()
        val update = pendingUpdate ?: return
        if (canInstallPackages()) {
            pendingUpdate = null
            installUpdate(update)
        }
    }

    override fun onDestroy() {
        discoveryGeneration++
        stopDiscovery()
        mainHandler.removeCallbacks(updateCheckTask)
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
        val serverUri = Uri.parse(url)
        currentServerHost = serverUri.host
        currentServerOrigin = if (serverUri.scheme != null && serverUri.authority != null) {
            "${serverUri.scheme}://${serverUri.authority}"
        } else {
            null
        }
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
        closeNavigationDrawer()
        loadingStatus.text = message
        loaderScreen.visibility = View.VISIBLE
        offlineScreen.visibility = View.GONE
        webView.visibility = View.GONE
        navigationBar.visibility = View.GONE
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
        closeNavigationDrawer()
        webView.stopLoading()
        webView.visibility = View.GONE
        loaderScreen.visibility = View.GONE
        navigationBar.visibility = View.GONE
        offlineScreen.visibility = View.VISIBLE
    }

    private fun createNavigationBar(density: Float): LinearLayout {
        val menuButton = TextView(this).apply {
            text = "☰"
            textSize = 25f
            gravity = Gravity.CENTER
            contentDescription = getString(R.string.open_navigation)
            setTextColor(getColor(R.color.app_heading))
            setOnClickListener { openNavigationDrawer() }
        }
        currentPathLabel = TextView(this).apply {
            text = "/"
            textSize = 12f
            setTextColor(getColor(R.color.app_secondary_text))
        }
        val titleBlock = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            addView(
                TextView(this@MainActivity).apply {
                    text = getString(R.string.app_name)
                    textSize = 17f
                    typeface = Typeface.create("sans-serif", Typeface.BOLD)
                    setTextColor(getColor(R.color.app_heading))
                },
            )
            addView(currentPathLabel)
        }
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(getColor(R.color.app_surface))
            visibility = View.GONE
            addView(
                menuButton,
                LinearLayout.LayoutParams(
                    (56 * density).toInt(),
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
            addView(
                titleBlock,
                LinearLayout.LayoutParams(
                    0,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    1f,
                ),
            )
        }
    }

    private fun applySystemThemeToPage(onApplied: () -> Unit) {
        val isDark =
            (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
                Configuration.UI_MODE_NIGHT_YES
        val css = if (isDark) {
            """
                :root {
                    color-scheme: dark !important;
                    --coride-surface: #1c1f26;
                    --coride-text: #f4f3ee;
                    --coride-muted: #c0c7d0;
                }
                html, body {
                    background: var(--coride-surface) !important;
                    color: var(--coride-text) !important;
                }
                p { color: var(--coride-muted) !important; }
                .mascot::before { color: rgb(244 243 238 / 8%) !important; }
            """.trimIndent()
        } else {
            """
                :root {
                    color-scheme: light !important;
                    --coride-surface: #f2f7f6;
                    --coride-text: #172f46;
                    --coride-muted: #60778a;
                }
                html, body {
                    background: var(--coride-surface) !important;
                    color: var(--coride-text) !important;
                }
                p { color: var(--coride-muted) !important; }
                .mascot::before { color: rgb(23 47 70 / 8%) !important; }
            """.trimIndent()
        }
        val script = """
            (function() {
                var style = document.getElementById('coride-android-theme');
                if (!style) {
                    style = document.createElement('style');
                    style.id = 'coride-android-theme';
                    (document.head || document.documentElement).appendChild(style);
                }
                style.textContent = ${JSONObject.quote(css)};
            })();
        """.trimIndent()
        webView.evaluateJavascript(script) { onApplied() }
    }

    private fun createNavigationDrawer(density: Float): LinearLayout {
        val drawer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(getColor(R.color.app_surface))
            elevation = 12 * density
        }
        drawer.addView(
            TextView(this).apply {
                text = getString(R.string.navigation_pages)
                textSize = 20f
                typeface = Typeface.create("sans-serif", Typeface.BOLD)
                setTextColor(getColor(R.color.app_heading))
                setPadding(
                    (20 * density).toInt(),
                    (28 * density).toInt(),
                    (20 * density).toInt(),
                    (16 * density).toInt(),
                )
            },
        )
        navigationDestinations.forEach { destination ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER_VERTICAL
                isClickable = true
                isFocusable = true
                setPadding(
                    (20 * density).toInt(),
                    (10 * density).toInt(),
                    (20 * density).toInt(),
                    (10 * density).toInt(),
                )
                val selectableBackground = TypedValue()
                if (theme.resolveAttribute(
                        android.R.attr.selectableItemBackground,
                        selectableBackground,
                        true,
                    )
                ) {
                    setBackgroundResource(selectableBackground.resourceId)
                }
                setOnClickListener { navigateToRoute(destination.path) }
            }
            row.addView(
                TextView(this).apply {
                    text = getString(destination.titleRes)
                    textSize = 16f
                    setTextColor(getColor(R.color.app_heading))
                },
            )
            row.addView(
                TextView(this).apply {
                    text = destination.path
                    textSize = 13f
                    setTextColor(getColor(R.color.app_secondary_text))
                },
            )
            drawer.addView(
                row,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    (64 * density).toInt(),
                ),
            )
        }
        return drawer
    }

    private fun openNavigationDrawer() {
        if (currentServerOrigin == null) return
        navigationScrim.visibility = View.VISIBLE
        navigationDrawer.visibility = View.VISIBLE
    }

    private fun closeNavigationDrawer() {
        navigationScrim.visibility = View.GONE
        navigationDrawer.visibility = View.GONE
    }

    private fun navigateToRoute(path: String) {
        val origin = currentServerOrigin
        if (origin == null) {
            Log.w(TAG, "Cannot open CoRide route without a connected server")
            return
        }
        loadServer("$origin$path", isFallback = loadingFallback)
    }

    private fun updateCurrentPath(url: String?) {
        val uri = url?.let(Uri::parse) ?: return
        currentPathLabel.text = uri.path?.takeIf(String::isNotEmpty) ?: "/"
    }

    private fun checkForUpdates() {
        if (
            updateCheckInProgress ||
            updateDownloadInProgress ||
            pendingUpdate != null ||
            isFinishing ||
            isDestroyed
        ) {
            return
        }
        updateCheckInProgress = true
        Thread({
            try {
                val update = releaseUpdater.findUpdate(BuildConfig.VERSION_NAME)
                mainHandler.post {
                    if (isDestroyed) return@post
                    updateCheckInProgress = false
                    if (update == null || update.versionName == rejectedUpdateVersion) return@post
                    versionLabel.text = getString(
                        R.string.update_available,
                        BuildConfig.VERSION_NAME,
                        update.versionName,
                    )
                    loadingStatus.text = getString(R.string.downloading_update)
                    downloadUpdate(update)
                }
            } catch (error: IOException) {
                Log.w(TAG, "Could not check GitHub for Android updates", error)
                mainHandler.post {
                    if (!isDestroyed) updateCheckInProgress = false
                }
            }
        }, "CoRide-release-check").start()
    }

    private fun downloadUpdate(update: GitHubReleaseUpdater.AvailableUpdate) {
        updateDownloadInProgress = true
        Thread({
            try {
                val apk = releaseUpdater.downloadAndValidate(update, BuildConfig.VERSION_CODE)
                mainHandler.post {
                    if (isDestroyed) return@post
                    updateDownloadInProgress = false
                    requestUpdateInstallation(PendingUpdate(apk, update.versionName))
                }
            } catch (error: IOException) {
                Log.e(TAG, "Could not download or validate the CoRide update", error)
                mainHandler.post {
                    if (isDestroyed) return@post
                    updateDownloadInProgress = false
                    rejectedUpdateVersion = update.versionName
                    loadingStatus.text = getString(R.string.update_failed)
                }
            }
        }, "CoRide-release-download").start()
    }

    private fun requestUpdateInstallation(update: PendingUpdate) {
        pendingUpdate = update
        if (!canInstallPackages()) {
            loadingStatus.text = getString(R.string.install_permission_required)
            try {
                startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:$packageName"),
                    ),
                )
            } catch (error: android.content.ActivityNotFoundException) {
                Log.e(TAG, "Android could not open app-install permission settings", error)
                Toast.makeText(this, R.string.install_permission_required, Toast.LENGTH_LONG).show()
            }
            return
        }
        pendingUpdate = null
        installUpdate(update)
    }

    private fun canInstallPackages(): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
            packageManager.canRequestPackageInstalls()
    }

    private fun installUpdate(update: PendingUpdate) {
        try {
            val installer = packageManager.packageInstaller
            val parameters = android.content.pm.PackageInstaller.SessionParams(
                android.content.pm.PackageInstaller.SessionParams.MODE_FULL_INSTALL,
            ).apply {
                setAppPackageName(packageName)
            }
            val sessionId = installer.createSession(parameters)
            installer.openSession(sessionId).use { session ->
                FileInputStream(update.apk).use { input ->
                    session.openWrite("base.apk", 0, update.apk.length()).use { output ->
                        input.copyTo(output)
                        session.fsync(output)
                    }
                }
                val callbackIntent = Intent(this, UpdateInstallReceiver::class.java)
                    .putExtra(UpdateInstallReceiver.EXTRA_VERSION, update.versionName)
                val mutabilityFlag = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    PendingIntent.FLAG_MUTABLE
                } else {
                    0
                }
                val callback = PendingIntent.getBroadcast(
                    this,
                    sessionId,
                    callbackIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT or mutabilityFlag,
                )
                session.commit(callback.intentSender)
            }
            loadingStatus.text = getString(R.string.install_confirmation)
        } catch (error: IOException) {
            Log.e(TAG, "Could not start Android package installation", error)
            loadingStatus.text = getString(R.string.update_failed)
        } catch (error: SecurityException) {
            Log.e(TAG, "Android denied package installation", error)
            loadingStatus.text = getString(R.string.update_failed)
        }
    }

    private companion object {
        const val SERVICE_TYPE = "_coride._tcp."
        const val DISCOVERY_TIMEOUT_MS = 15_000L
        const val UPDATE_CHECK_INTERVAL_MS = 120_000L
        const val FALLBACK_URL = "https://coride-sep.vercel.app/"
        const val TAG = "CoRide"
    }
}
