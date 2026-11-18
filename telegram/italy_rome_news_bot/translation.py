"""Translate Italian headlines on the CPU using Helsinki-NLP's OPUS-MT model."""

import os
from functools import lru_cache
from pathlib import Path

import ctranslate2
import sentencepiece
from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

MODEL = "VoragoStudios/gct-opus-mt-tc-big-it-en-ct2"
REVISION = "0f3d97f59e65e95730fc784a2060aacc42044237"
FILES = ["model.bin", "config.json", "shared_vocabulary.json", "source.spm", "target.spm"]


class HeadlineTranslator:
    def __init__(self):
        options = dict(repo_id=MODEL, revision=REVISION, allow_patterns=FILES, token=False)
        try:
            folder = Path(snapshot_download(**options, local_files_only=True))
        except LocalEntryNotFoundError:
            folder = Path(snapshot_download(**options))
        self.source = sentencepiece.SentencePieceProcessor(model_file=str(folder / "source.spm"))
        self.target = sentencepiece.SentencePieceProcessor(model_file=str(folder / "target.spm"))
        self.model = ctranslate2.Translator(
            str(folder), device="cpu", compute_type="auto", intra_threads=min(4, os.cpu_count() or 1)
        )

    @lru_cache(maxsize=128)
    def translate(self, titles: tuple[str, ...]) -> tuple[str, ...]:
        # This Marian model expects the source's end-of-sentence token explicitly.
        tokens = [self.source.encode(title, out_type=str) + ["</s>"] for title in titles]
        results = self.model.translate_batch(tokens, beam_size=4, max_decoding_length=256)
        english = tuple(" ".join(self.target.decode(r.hypotheses[0]).split()) for r in results)
        if len(english) != len(titles) or not all(english):
            raise ValueError("Incomplete headline translation")
        return english
