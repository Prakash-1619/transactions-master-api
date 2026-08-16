import s3fs

def get_s3_fs():
    """Returns an authenticated s3fs FileSystem for Cloudflare R2."""
    return s3fs.S3FileSystem(
        key="c198c85bd01da0931eae24009fb2100b",
        secret="826187ffaee4742816f65ca4ebe149902db75ac52dbb81606bb34fe8bae4a57c",
        client_kwargs={
            "endpoint_url": "https://ef8eef61229ee8854b4237f6949e50d8.r2.cloudflarestorage.com/truestates-re-analytics",
            "region_name": "auto",
        },
        config_kwargs={"signature_version": "s3v4"},
    )

def get_storage_options():
    """Returns storage_options dict for pandas read_parquet/to_parquet."""
    return {
        "key": "c198c85bd01da0931eae24009fb2100b",
        "secret": "826187ffaee4742816f65ca4ebe149902db75ac52dbb81606bb34fe8bae4a57c",
        "client_kwargs": {
            "endpoint_url": "https://ef8eef61229ee8854b4237f6949e50d8.r2.cloudflarestorage.com/truestates-re-analytics",
            "region_name": "auto",
        },
        "config_kwargs": {"signature_version": "s3v4"}
    }
