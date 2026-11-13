import java.net.URI

plugins {
    id("com.android.application")
}

val serverUrl = providers.gradleProperty("mobileServerUrl")
    .orElse(providers.environmentVariable("MOBILE_SERVER_URL"))
    .getOrElse("")
    .trim()

if (serverUrl.isNotEmpty()) {
    val uri = URI(serverUrl)
    require(
        uri.scheme in setOf("http", "https") &&
            !uri.host.isNullOrBlank() &&
            uri.userInfo == null &&
            uri.path.orEmpty() in setOf("", "/") &&
            uri.query == null &&
            uri.fragment == null,
    ) {
        "mobileServerUrl must be an HTTP(S) origin without a path, query, or fragment."
    }
}

val escapedServerUrl = serverUrl
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")
val mobileVersionCode = providers.gradleProperty("mobileVersionCode")
    .getOrElse("1")
    .toInt()
val mobileVersionName = providers.gradleProperty("mobileVersionName")
    .getOrElse("0.1.0")

require(mobileVersionCode > 0) {
    "mobileVersionCode must be a positive integer."
}

android {
    namespace = "com.coride.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.coride.app"
        minSdk = 24
        targetSdk = 35
        versionCode = mobileVersionCode
        versionName = mobileVersionName
        buildConfigField("String", "SERVER_URL", "\"$escapedServerUrl\"")
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
