# Developing V2 Connectors
## Intro
The Unstructured open source repo processes documents (artifacts) in a pipeline. The Source and Destination connectors sit at the front and back of the pipeline. For more details see below (COMING SOON).

## Simplest Example of a Pipeline
The simplest example of a pipeline would start with a local source connector, followed by a partioner, and then end with a local destination connector. Here is what the code to run this would look like:

>*** This is the type of Python file you'll want to run during development so that you can iterate on your connector.

`local.py`

```
from unstructured.ingest.v2.interfaces import ProcessorConfig
from unstructured.ingest.v2.pipeline.pipeline import Pipeline
from unstructured.ingest.v2.processes.connectors.local import (
    LocalConnectionConfig,
    LocalDownloaderConfig,
    LocalIndexerConfig,
    LocalUploaderConfig,
)
from unstructured.ingest.v2.processes.partitioner import PartitionerConfig

if __name__ == "__main__":
    Pipeline.from_configs(
        context=ProcessorConfig(
            verbose=True,
            work_dir="local-working-dir",
            reprocess=True,
            re_download=True,
        ),
        source_connection_config=LocalConnectionConfig(),
        indexer_config=LocalIndexerConfig(input_path="example-docs/fake-text.txt"),
        downloader_config=LocalDownloaderConfig(),
        partitioner_config=PartitionerConfig(),
        uploader_config=LocalUploaderConfig(output_dir="local-working-dir/output"),
    ).run()
```
You can run this with `python local.py` (Adjust the `input_path` and `output_dir` as appropriate.)

The result would be a partitioned `fake-text.txt.json` file in the `local-output` directory.



Notice that the pipeline runs the following:

* context - The ProcessorConfig runs the pipeline. The arguments are related to the overall pipeline. We added some optional args to make development easier.
* source_connection - Takes arguments needed to connect to the source. Local files don't need anything here. Other connectors will.
* indexer - Takes the files in the `input_path` and creates .json files that point the downloader step to the right files 
* downloader - This does the actual downloading of the raw files (for non-blob files it may do something different like create a .txt file for every row in a source table)
* partitioner - Partitions the downloaded file provided it is a partionable file type.
* chunker/embedder - *Not represented here* but often needed to prepare files for upload to a vector database.
* stager - *Not represented here* but is often used to prepare partitioned files for upload.
* uploader - Uploads the blob-like files to the `output_dir`.


If you look at the folders/files in `local-working-dir` you will see the files that the pipeline creates as it runs.

```
local-working-dir
- index
  - a4a1035d57ed.json
- output
  - fake-text.txt.json
- partition
  - 36caa9b04378.json
```

(Note that the index and partition file names are deterministic and based on the BLABLABLA) In the case of the local source connector, it won't *download* files because they are already local. But for other source connectors there will be a `download` folder. Also note that the final file is named based on the original file with a `.json` extension since it has been partitioned. Not all output files will be named the same as the input file. An example is a table as a source file, the output will be BLABLABLA.

You can see the source/destination connector file that it runs here:

https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/ingest/v2/processes/connectors/local.py

If you look through the file you will notice these Classes (actually @dataclasses because BLABLABLA) and functions

* LocalAccessConfig - This usually holds passwords, tokens, etc. This data gets hidden in all logs (and encrypted in our platform solution)

* LocalConnectionConfig - Username, host, port, etc. Anything needed for connecting to the service. It also imports the AccessConfig 

* LocalIndexerConfig - Holds information

* LocalIndexer - BLABLABLA

* LocalDownloaderConfig

* LocalDownloader

* LocalUploaderConfig

* LocalUploader

* local_source_entry

* local_destination_entry



## Building a Destination Connector
We'll start with building a Destination Connector because those are the easier to build than Source Connectors.

In this case we'll use the Chroma vector database destination because:

* The service can be hosted locally. !!! https://docs.trychroma.com/guides
* We can show off the chunking and embedding step (used for vector database destinations)
* It uses a staging step to prepare the artifacts before uploading
* You can examine the Chroma database file easily since its just a sqlite database


The python file to iterate on development looks like this:

`chroma.py`

```
import random # So we get a new Chroma collections on every run

from unstructured.ingest.v2.interfaces import ProcessorConfig
from unstructured.ingest.v2.pipeline.pipeline import Pipeline
from unstructured.ingest.v2.processes.chunker import ChunkerConfig
from unstructured.ingest.v2.processes.connectors.chroma import (
    ChromaAccessConfig,
    ChromaConnectionConfig,
    ChromaUploaderConfig,
    ChromaUploadStagerConfig,
)
from unstructured.ingest.v2.processes.connectors.local import (
    LocalConnectionConfig,
    LocalDownloaderConfig,
    LocalIndexerConfig,
)
from unstructured.ingest.v2.processes.embedder import EmbedderConfig
from unstructured.ingest.v2.processes.partitioner import PartitionerConfig

if __name__ == "__main__":
    Pipeline.from_configs(
        context=ProcessorConfig(
            verbose=True,
            work_dir="chroma-working-dir",
            reprocess=True,
            re_download=True,
        ),
        source_connection_config=LocalConnectionConfig(),
        indexer_config=LocalIndexerConfig(input_path="example-docs/fake-text.txt"),
        downloader_config=LocalDownloaderConfig(),
        partitioner_config=PartitionerConfig(),

        chunker_config=ChunkerConfig(
            chunking_strategy="basic",
        ),
        embedder_config=EmbedderConfig(embedding_provider="langchain-huggingface"),
        
        destination_connection_config=ChromaConnectionConfig(
            access_config=ChromaAccessConfig(settings=None, headers=None),
            host="localhost",
            port=8000,
            collection_name=f"test-collection-{random.randint(1000,9999)}",
        ),
        stager_config=ChromaUploadStagerConfig(),
        uploader_config=ChromaUploaderConfig(batch_size=10),
    ).run()

```

Notice how the top part looks similar to the local connector running file. But now we are adding a chunker and an embedder. And the destination connection is for the Chroma uploader. Also note that there is a stager_config. This is where we prepare the document/artifact in a custom way before uploading BLABLABLA.

Let's run it.



* blabla make sure you have run `pip install "unstructured[chroma]"`

* in a separate terminal (with chroma installed) run
`./scripts/chroma-test-helpers/create-and-check-chroma.sh chroma-db-file`
the service should now be running on port 8000

* `python chroma.py`
* You can examine the resulting sqlite database (`chroma.sqlite3`) in the `chroma-db-file` directory if you want to see the results.


Let's look at the python file that it runs BLABLABLA

https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/ingest/v2/processes/connectors/chroma.py

* ChromaAccessConfig - Needed for connecting to Chroma. Usually sensitive attributes that will be hidden.

* ChromaConnectionConfig - Non sensitive attributes. `collection_name` does not have a default value. `access_config` imports the ChromaAccessConfig and hides the values via `enhanced_field(sensitive=True)`

* ChromaUploadStagerConfig - The Stager config. Didn't need anything for Chroma.

* ChromaUploadStager - The conform_dict is the critical method here. It takes the file we get from the Embedder step and prepares it for upload to the Chroma database. But it does not upload it. It saves the file to the `upload_stage` directory. The file type can be whatever makes sense for the Uploader phase.

* ChromaUploaderConfig - Attributes that are necessary for the upload stage specifically. The ChromaUploader will be upserting artifacts in batches.

* ChromaUploader - Connects to the Client. And uploads artifacts. Note that it does the minimum amount of processing possible to the artifacts before uploading. The Stager phase is responsible for preparing artifacts. Chroma wants artifacts in a dictionary of lists so we do have to create that in the Uploader since there is not a practical way to store that in a file.

* chroma_destination_entry - Registers the Chroma destination connector with the pipeline. (!!! LINK `unstructured/ingest/v2/processes/connectors/__init__.py`)

Note that the `chroma.py` file imports the official Chroma python package when it *creates* the client and not at the top of the file. This is so that BLABLABLA

Let's take a quick look at the `upload_stage` in  working directory:
```
chroma-working-dir
- chunk
  - f0987c36c3b0.json
- embed
  - dafc7add1d21.json
- index
  - a4a1035d57ed.json
- partition
  - 36caa9b04378.json
- upload_stage
  - e17715933baf.json
```
`e17715933baf.json` in the `upload_stage` is a `.json` file which is appropriate for this destination connector. But it could very well be a `.csv` if the uploader is a relational database. Or if the destination is blob(file) storage, like AWS S3, you may not need the Staging phase. The embed `.json` file would be uploaded directly.

When you make a **new** Destination Connector you will need these files first:

* `unstructured/ingest/v2/processes/connectors/your_connector.py`
* And add that to: `unstructured/ingest/v2/processes/connectors/__init__.py`
* Your python file to iterate on development. You can call it `unstructured/ingest/v2/examples/example_your_connector.py`
* And some form of **live connection** to the Destination service. In the case of Chroma we have a local service running. Often we will run a docker container (Elasticsearch). At other times we will use a hosted service if there is no docker image (Pinecone).

Once the connector is worked out with those files, you will need to add a few more files. 

* `unstructured/ingest/v2/cli/cmds/your_connector.py`
* Add that to: `unstructured/ingest/v2/cli/cmds/__init__.py`
* Makefile
* Manifest.in
* setup.py
* your_connector.in (to create the requirements file)
* Documentation

The CLI file. This allows the connector to be run via the command line. All the arguments for the connector need to be exposed.

`unstructured/ingest/v2/cli/cmds/your_connector.py`


### Intrgration Test
And lastly we need an executable .sh file that runs in CI/CD as an integration? test.

`test_unstructured_ingest/dest/weaviate.sh` is a good example because it uses a Docker container to act as the Weaviate service. 

If you run `./test_unstructured_ingest/dest/weaviate.sh` from the root it will spin up a docker container. Create a blank `elements` collection based on the schema. Partition `fake-memo.pdf`. Embed the artifact with vector embeddings. Upload the artifact to the Weaviate vector database. And then it runs `/python/test-ingest-weaviate-output.py` which counts the number of embeddings that were loaded.

In an ideal world, for a vector database destination, the test will also do a vector search and validate the results. (`scripts/elasticsearch-test-helpers/destination_connector/test-ingest-elasticsearch-output.py` is an example of this.)

If you can run the integration test successfully then most of the files should be in order.

## Building a Source Connector

The Source Connector example we will use is `onedrive.py`. The S3 connector might be a simpler example, but it relies on the incredibly useful fsspec package.
https://filesystem-spec.readthedocs.io/en/latest/ 
If your source connector can take advantage of fsspec, then S3 might be a good example.


The Source Connector is similar to the Destination Connector instructions above.

But the key difference is the Indexer. The Indexer essentially gets a list of the documents/artifacts in the Source service. (in the case of a local connector it would be like a bash `ls` command). It then creates individual files for each artifact that need to be downloaded.This is so that the next phase, the Downloader phase, can be scaled out with multiple workers. The Indexer phase needs to return pointers to those artifacts in the shape of the FileData object, which it then downloads as `.json` files.

The Downloader then uses the `.json` files that the Indexer created and downloads the raw files (in the case of a blob type file, .pdf, .txt) or as individual rows in a table, or any other needed format.

Here are some of the file types it can download and partition. 
https://github.com/Unstructured-IO/unstructured/blob/0c562d80503f6ef96504c6e38f27cfd9da8761df/unstructured/file_utils/filetype.py

The Indexer files (resulting `.json` files in the index folder) also contain metadata that will be used to determine if the files have already been processed.












