package com.coride.app

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

internal class GitHubReleaseUpdater(private val context: Context) {
    data class AvailableUpdate(
        val versionName: String,
        val downloadUrl: String,
        val sha256: String?,
    )

    fun findUpdate(currentVersionName: String): AvailableUpdate? {
        val connection = (URL(RELEASE_API_URL).openConnection() as HttpURLConnection).apply {
            connectTimeout = CONNECTION_TIMEOUT_MS
            readTimeout = CONNECTION_TIMEOUT_MS
            requestMethod = "GET"
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("X-GitHub-Api-Version", GITHUB_API_VERSION)
        }

        try {
            if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                throw IOException("GitHub release API returned HTTP ${connection.responseCode}")
            }
            val body = connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            val release = try {
                JSONObject(body)
            } catch (error: JSONException) {
                throw IOException("GitHub returned invalid release data", error)
            }
            val tagName = release.optString("tag_name")
            val versionMatch = VERSION_TAG.matchEntire(tagName)
                ?: throw IOException("GitHub release has an invalid stable version tag")
            val versionName = versionMatch.groupValues.drop(1).joinToString(".")
            if (compareVersions(versionName, currentVersionName) <= 0) return null

            val assets = try {
                release.getJSONArray("assets")
            } catch (error: JSONException) {
                throw IOException("GitHub release does not contain APK assets", error)
            }
            val apkAsset = try {
                (0 until assets.length())
                    .map { assets.getJSONObject(it) }
                    .firstOrNull { it.optString("name") == APK_ASSET_NAME }
            } catch (error: JSONException) {
                throw IOException("GitHub returned invalid APK asset data", error)
            } ?: throw IOException("GitHub release does not contain $APK_ASSET_NAME")
            val downloadUrl = apkAsset.optString("browser_download_url")
            if (!isTrustedReleaseUrl(downloadUrl)) {
                throw IOException("GitHub release contains an untrusted APK URL")
            }
            val digest = apkAsset.optString("digest")
                .takeIf { it.startsWith("sha256:", ignoreCase = true) }
                ?.substringAfter(':')
                ?.lowercase()

            return AvailableUpdate(versionName, downloadUrl, digest)
        } finally {
            connection.disconnect()
        }
    }

    fun downloadAndValidate(update: AvailableUpdate, installedVersionCode: Int): File {
        val partialFile = File(context.cacheDir, "coride-update-${update.versionName}.apk.part")
        val apkFile = File(context.cacheDir, "coride-update-${update.versionName}.apk")
        if (partialFile.exists() && !partialFile.delete()) {
            throw IOException("Could not clear the partial CoRide update")
        }

        val connection = (URL(update.downloadUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = CONNECTION_TIMEOUT_MS
            readTimeout = DOWNLOAD_TIMEOUT_MS
            instanceFollowRedirects = true
            requestMethod = "GET"
            setRequestProperty("User-Agent", USER_AGENT)
        }
        try {
            if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                throw IOException("GitHub APK download returned HTTP ${connection.responseCode}")
            }
            val finalUri = Uri.parse(connection.url.toString())
            if (finalUri.scheme != "https" || finalUri.host !in ALLOWED_DOWNLOAD_HOSTS) {
                throw IOException("GitHub redirected the APK download to an untrusted host")
            }
            connection.inputStream.use { input ->
                FileOutputStream(partialFile).use { output -> input.copyTo(output) }
            }
            if (!partialFile.isFile || partialFile.length() == 0L) {
                throw IOException("GitHub returned an empty APK")
            }
            update.sha256?.let { expected ->
                if (!sha256(partialFile).equals(expected, ignoreCase = true)) {
                    throw IOException("Downloaded APK failed its SHA-256 check")
                }
            }
            validatePackage(partialFile, update, installedVersionCode)
            if (apkFile.exists() && !apkFile.delete()) {
                throw IOException("Could not replace the cached CoRide update")
            }
            if (!partialFile.renameTo(apkFile)) {
                throw IOException("Could not save the downloaded CoRide update")
            }
            return apkFile
        } catch (error: IOException) {
            partialFile.delete()
            throw error
        } finally {
            connection.disconnect()
        }
    }

    private fun validatePackage(
        apk: File,
        update: AvailableUpdate,
        installedVersionCode: Int,
    ) {
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION")
            PackageManager.GET_SIGNATURES
        }
        val archiveInfo = context.packageManager.getPackageArchiveInfo(apk.absolutePath, flags)
            ?: throw IOException("Downloaded file is not a valid Android APK")
        if (archiveInfo.packageName != context.packageName) {
            throw IOException("Downloaded APK is for a different Android app")
        }
        if (archiveInfo.versionName != update.versionName) {
            throw IOException("Downloaded APK version does not match the GitHub release")
        }
        val archiveVersionCode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            archiveInfo.longVersionCode
        } else {
            archiveInfo.versionCode.toLong()
        }
        if (archiveVersionCode <= installedVersionCode.toLong()) {
            throw IOException("GitHub APK version code is not newer than the installed app")
        }

        val installedInfo = try {
            context.packageManager.getPackageInfo(context.packageName, flags)
        } catch (error: PackageManager.NameNotFoundException) {
            throw IOException("Could not verify the installed CoRide app", error)
        }
        val installedSignatures = signatures(installedInfo)
            ?: throw IOException("Could not verify the installed CoRide signing certificate")
        val updateSignatures = signatures(archiveInfo)
            ?: throw IOException("Could not verify the update signing certificate")
        if (installedSignatures.isEmpty() || installedSignatures != updateSignatures) {
            throw IOException("GitHub APK signing certificate does not match this installation")
        }
    }

    private fun signatures(packageInfo: PackageInfo): Set<String>? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            return packageInfo.signingInfo?.apkContentsSigners
                ?.map { it.toCharsString() }
                ?.toSet()
        }
        @Suppress("DEPRECATION")
        return packageInfo.signatures?.map { it.toCharsString() }?.toSet()
    }

    private fun sha256(file: File): String {
        val digest = try {
            MessageDigest.getInstance("SHA-256")
        } catch (error: java.security.NoSuchAlgorithmException) {
            throw IOException("SHA-256 is unavailable on this device", error)
        }
        file.inputStream().use { input ->
            val buffer = ByteArray(BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun compareVersions(left: String, right: String): Int {
        val leftParts = left.split('.').map { it.toLongOrNull() }
        val rightParts = right.split('.').map { it.toLongOrNull() }
        for (index in 0..2) {
            val leftPart = leftParts[index]
                ?: throw IOException("GitHub release version is out of range")
            val rightPart = rightParts[index]
                ?: throw IOException("Installed app version is invalid")
            val comparison = leftPart.compareTo(rightPart)
            if (comparison != 0) return comparison
        }
        return 0
    }

    private fun isTrustedReleaseUrl(value: String): Boolean {
        val uri = Uri.parse(value)
        return uri.scheme == "https" &&
            uri.host.equals(GITHUB_HOST, ignoreCase = true) &&
            uri.path.orEmpty().startsWith(RELEASE_DOWNLOAD_PATH)
    }

    private companion object {
        const val APK_ASSET_NAME = "app-debug.apk"
        const val BUFFER_SIZE = 8 * 1024
        const val CONNECTION_TIMEOUT_MS = 15_000
        const val DOWNLOAD_TIMEOUT_MS = 60_000
        const val GITHUB_API_VERSION = "2022-11-28"
        const val GITHUB_HOST = "github.com"
        const val RELEASE_API_URL =
            "https://api.github.com/repos/alcoholic-lain/CORIDE-SEP/releases/latest"
        const val RELEASE_DOWNLOAD_PATH = "/alcoholic-lain/CORIDE-SEP/releases/download/"
        const val USER_AGENT = "CoRide-Android"
        val ALLOWED_DOWNLOAD_HOSTS = setOf(
            GITHUB_HOST,
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
        )
        val VERSION_TAG = Regex("^v(\\d+)\\.(\\d+)\\.(\\d+)$")
    }
}
