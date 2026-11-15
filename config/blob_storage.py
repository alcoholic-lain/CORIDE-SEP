from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from vercel.blob import sync as blob


class PrivateVercelBlobStorage(Storage):
    def _open(self, name, mode="rb"):
        result = blob.get_blob(name, access="private")
        return ContentFile(result.body, name=name)

    def _save(self, name, content):
        result = blob.put_blob(
            name,
            content.chunks(),
            access="private",
            content_length=content.size,
            content_type=getattr(
                content,
                "validated_content_type",
                getattr(content, "content_type", None),
            ),
        )
        return result.pathname

    def delete(self, name):
        blob.delete_blob(name)

    def exists(self, name):
        try:
            blob.head_blob(name)
        except blob.BlobNotFoundError:
            return False
        return True

    def size(self, name):
        return blob.head_blob(name).size
