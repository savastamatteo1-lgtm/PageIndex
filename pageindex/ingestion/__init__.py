# pageindex.ingestion -- Batch ingestion pipeline for Italian legal PDFs.

from .models import ChunkData, DocumentPipeline
from .pipeline import ingest
from .stages import process_single_document
