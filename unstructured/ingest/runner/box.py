import logging
import typing as t

from unstructured.ingest.interfaces import PartitionConfig, ReadConfig
from unstructured.ingest.logger import ingest_log_streaming_init, logger
from unstructured.ingest.processor import process_documents
from unstructured.ingest.runner.utils import update_download_dir_remote_url
from unstructured.ingest.runner.writers import writer_map


def box(
    verbose: bool,
    read_config: ReadConfig,
    partition_config: PartitionConfig,
    remote_url: str,
    recursive: bool,
    box_app_config: t.Optional[str],
    writer_type: t.Optional[str] = None,
    writer_kwargs: t.Optional[dict] = None,
    **kwargs,
):
    writer_kwargs = writer_kwargs if writer_kwargs else {}
    ingest_log_streaming_init(logging.DEBUG if verbose else logging.INFO)

    read_config.download_dir = update_download_dir_remote_url(
        connector_name="azure",
        read_config=read_config,
        remote_url=remote_url,
        logger=logger,
    )

    from unstructured.ingest.connector.box import BoxSourceConnector, SimpleBoxConfig

    source_doc_connector = BoxSourceConnector(  # type: ignore
        read_config=read_config,
        connector_config=SimpleBoxConfig(
            path=remote_url,
            recursive=recursive,
            access_kwargs={"box_app_config": box_app_config},
        ),
        partition_config=partition_config,
    )

    dest_doc_connector = None
    if writer_type:
        writer = writer_map[writer_type]
        dest_doc_connector = writer(**writer_kwargs)

    process_documents(
        source_doc_connector=source_doc_connector,
        partition_config=partition_config,
        verbose=verbose,
        dest_doc_connector=dest_doc_connector,
    )