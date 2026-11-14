package com.coride.app

import android.net.Uri
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

internal class GitHubReleaseUpdater {
    data class AvailableUpdate(
        val versionName: String,
        val releaseUrl: String,
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

            val hasApk = try {
                val assets = release.getJSONArray("assets")
                (0 until assets.length())
                    .map { assets.getJSONObject(it) }
                    .any { it.optString("name") == APK_ASSET_NAME }
            } catch (error: JSONException) {
                throw IOException("GitHub returned invalid release asset data", error)
            }
            if (!hasApk) throw IOException("GitHub release does not contain $APK_ASSET_NAME")

            val releaseUrl = release.optString("html_url")
            if (!isTrustedReleasePage(releaseUrl, tagName)) {
                throw IOException("GitHub returned an untrusted release page URL")
            }
            return AvailableUpdate(versionName, releaseUrl)
        } finally {
            connection.disconnect()
        }
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

    private fun isTrustedReleasePage(value: String, tagName: String): Boolean {
        val uri = Uri.parse(value)
        return uri.scheme == "https" &&
            uri.host.equals(GITHUB_HOST, ignoreCase = true) &&
            uri.path == "$RELEASE_PAGE_PATH$tagName"
    }

    private companion object {
        const val APK_ASSET_NAME = "app-debug.apk"
        const val CONNECTION_TIMEOUT_MS = 15_000
        const val GITHUB_API_VERSION = "2022-11-28"
        const val GITHUB_HOST = "github.com"
        const val RELEASE_API_URL =
            "https://api.github.com/repos/alcoholic-lain/CORIDE-SEP/releases/latest"
        const val RELEASE_PAGE_PATH = "/alcoholic-lain/CORIDE-SEP/releases/tag/"
        const val USER_AGENT = "CoRide-Android"
        val VERSION_TAG = Regex("^v(\\d+)\\.(\\d+)\\.(\\d+)$")
    }
}
