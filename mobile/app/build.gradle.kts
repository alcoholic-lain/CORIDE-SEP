import java.net.URI
import org.gradle.api.DefaultTask
import org.gradle.api.file.DirectoryProperty
import org.gradle.api.file.RegularFileProperty
import org.gradle.api.tasks.InputFile
import org.gradle.api.tasks.OutputDirectory
import org.gradle.api.tasks.PathSensitive
import org.gradle.api.tasks.PathSensitivity
import org.gradle.api.tasks.TaskAction

plugins {
    id("com.android.application")
}

abstract class PrepareLoaderAsset : DefaultTask() {
    @get:InputFile
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val loaderHtml: RegularFileProperty

    @get:OutputDirectory
    abstract val outputDirectory: DirectoryProperty

    @TaskAction
    fun copyLoaderHtml() {
        val destination = outputDirectory.file("coride-loader.html").get().asFile
        destination.parentFile.mkdirs()
        loaderHtml.get().asFile.copyTo(destination, overwrite = true)
    }
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
val mobileDebugKeystore = providers.gradleProperty("mobileDebugKeystore")
    .orElse(providers.environmentVariable("MOBILE_DEBUG_KEYSTORE"))
    .getOrElse("")
    .trim()

require(mobileVersionCode > 0) {
    "mobileVersionCode must be a positive integer."
}
if (mobileDebugKeystore.isNotEmpty()) {
    require(file(mobileDebugKeystore).isFile) {
        "mobileDebugKeystore must point to an existing keystore file."
    }
}

val prepareLoaderAsset = tasks.register<PrepareLoaderAsset>("prepareCorideLoaderAsset") {
    loaderHtml.set(rootProject.file("../coride-loader.html"))
    outputDirectory.set(layout.buildDirectory.dir("generated/coride-loader-assets"))
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

    if (mobileDebugKeystore.isNotEmpty()) {
        signingConfigs {
            create("persistentDebug") {
                storeFile = file(mobileDebugKeystore)
                storePassword = "android"
                keyAlias = "androiddebugkey"
                keyPassword = "android"
            }
        }
        buildTypes {
            getByName("debug") {
                signingConfig = signingConfigs.getByName("persistentDebug")
            }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(
            prepareLoaderAsset,
            PrepareLoaderAsset::outputDirectory,
        )
    }
}
