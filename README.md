# polarsteps-tts

Convert posts from a public Polarsteps trip into MP3 files via a local
text-to-speech engine — listen to your travel journals as audiobooks.

> **Status:** V1 functional. Tested end-to-end on a 31-step / 128k-character
> trip → 31 tagged MP3 files in a single command. Audio output uses
> [Voxtral-4B-TTS-2603](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603)
> served locally via [vLLM-Omni](https://github.com/vllm-project/vllm-omni).

---

## Requirements

- **Python 3.11+** with [`uv`](https://github.com/astral-sh/uv) (recommended)
  or `pip`
- **NVIDIA GPU with ≥ 16 GB VRAM** (24 GB used during validation on
  RTX 5090 Laptop)
- **CUDA-capable PyTorch environment** for the Voxtral server
- **`libsndfile ≥ 1.1`** (for MP3 encoding via `soundfile`) — usually
  bundled with the `soundfile` wheel, no system install needed.

The project itself is a pure HTTP client. All GPU/Voxtral dependencies
live in a separate Python venv that you start once and leave running.

---

## Installation

### 1. Client (this project)

```bash
git clone <this-repo>
cd polarsteps-tts
uv sync                    # or: python -m venv .venv && pip install -e .
source .venv/bin/activate
```

### 2. Voxtral server (one-time)

The TTS server needs its own venv with `vllm` and `vllm-omni`. **Pin both
on the same major.minor**: `vllm-omni 0.20` does not yet implement abstract
methods that `vllm 0.21` introduces, and the server will crash at boot.

```bash
python3.11 -m venv ~/venvs/vllm-omni
source ~/venvs/vllm-omni/bin/activate
pip install --upgrade pip
pip install "vllm==0.20.2" "vllm-omni==0.20.0"
```

Download the model weights (~7.5 GB) once:

```bash
huggingface-cli login                          # only if not already done
huggingface-cli download mistralai/Voxtral-4B-TTS-2603 \
  --local-dir /ai/models/tts/Voxtral-4B-TTS-2603
```

Then start the server (keeps running in its terminal):

```bash
./scripts/serve-voxtral.sh
```

The script activates the venv, runs a vllm/vllm-omni version sanity
check, and launches `vllm serve` with the configuration validated for
24 GB VRAM (`--gpu-memory-utilization 0.45 --max-model-len 4096`).
Override defaults with environment variables if needed:

```bash
PORT=9000 GPU_MEM=0.4 VOXTRAL_MODEL_DIR=/path/to/model ./scripts/serve-voxtral.sh
```

When you see `Uvicorn running on http://0.0.0.0:8091`, the server is ready.

---

## Quick start

```bash
# 1. Inspect a trip (no audio synthesis)
polarsteps-tts fetch https://www.polarsteps.com/<user>/<trip-id>-<slug>

# 2. Synthesize a single step (good for spot-checking quality)
polarsteps-tts synthesize-step <URL> 0

# 3. Synthesize the whole trip into per-step MP3s with ID3 tags
polarsteps-tts synthesize-trip <URL>
```

Output lands in `./out/<trip-slug>/00_<step-slug>.mp3`,
`01_<step-slug>.mp3`, etc.

---

## Commands

### `fetch <URL>`

Downloads the trip metadata and prints a summary (name, author, date
range, step count, estimated audio duration). Caches the payload locally.

```bash
polarsteps-tts fetch <URL>
polarsteps-tts fetch <URL> --no-cache    # bypass cache entirely
polarsteps-tts fetch <URL> --refresh     # force re-fetch, overwrite cache
```

### `synthesize-step <URL> <STEP_INDEX>`

Synthesizes one step into a single audio file. `STEP_INDEX` is 0-based.
Useful for iterating on voice or audio quality without burning GPU time
on a whole trip.

```bash
polarsteps-tts synthesize-step <URL> 0
polarsteps-tts synthesize-step <URL> 0 --voice fr_male
polarsteps-tts synthesize-step <URL> 0 --no-intro
polarsteps-tts synthesize-step <URL> 0 --format wav
polarsteps-tts synthesize-step <URL> 0 --speed 1.25
polarsteps-tts synthesize-step <URL> 0 --out ./my-output
```

### `synthesize-trip <URL>`

Synthesizes every step of a trip that has narratable text, in order.
Continues on per-step failure (errors collected in the final summary).
Shows a rich progress bar.

```bash
polarsteps-tts synthesize-trip <URL>
polarsteps-tts synthesize-trip <URL> --voice fr_female
polarsteps-tts synthesize-trip <URL> --format wav --out ./my-trip
polarsteps-tts synthesize-trip <URL> --no-tts-cache    # force re-synthesis
```

### Common options

| Flag | Default | Effect |
|---|---|---|
| `--voice <id>` | `fr_female` | Voxtral voice preset (`fr_female`, `fr_male`, `neutral_female`, `casual_male`, …). The Voxtral server exposes 20 presets — `curl http://localhost:8091/v1/audio/voices` lists them. |
| `--out <path>` | `./out` | Output directory. Files are written under `<out>/<trip-slug>/`. |
| `--format mp3\|wav` | `mp3` | Output audio format. MP3 includes ID3 tags. |
| `--speed <float>` | `1.0` | Playback speed (Voxtral). Range `0.25`–`4.0`. Below 1.0 = slower, above 1.0 = faster. Changes invalidate the audio cache. |
| `--voxtral-url <url>` | `http://localhost:8091` | Override if the Voxtral server runs elsewhere. |
| `--no-cache` | off | Skip the trip payload cache. |
| `--refresh` | off | Re-fetch the trip and overwrite the cached payload. |
| `--no-tts-cache` | off | Skip the per-chunk audio cache and re-synthesize every chunk. |
| `--no-intro` | off | Skip the spoken intro (`"Étape N : <step name>. Le DD month YYYY, à <location>."`) before the body. |

---

## Output

```
out/
└── <trip-slug>/
    ├── 00_<step-slug>.mp3      # ID3 tags: TIT2, TALB, TPE1, TRCK
    ├── 01_<step-slug>.mp3
    ├── …                       # silent steps (no description) keep their slot:
    │                           # the next step is `03_…` not `02_…`
    └── 30_<step-slug>.mp3
```

**Audio characteristics:**

- **MP3** — 24 kHz mono, MPEG Layer III via `soundfile` at compression
  level 0.2 (≈ LAME `qscale 2`, high-quality VBR ~150 kbps).
- **0.5 s** of silence at the start and end of each track, **0.4 s**
  between paragraphs (mandatory: masks Voxtral's slight inter-chunk
  timbre variation; without this, multi-chunk steps sound patched).
- **ID3v2 tags** (MP3 only):
  - `TIT2` — step name
  - `TALB` — trip name
  - `TPE1` — trip author's first name
  - `TRCK` — step position (1-based, in the trip's sorted order)

---

## Caches

Caches live under `$XDG_CACHE_HOME/polarsteps-tts/` (defaults to
`~/.cache/polarsteps-tts/`):

- **`trips/<trip-id>.json`** — raw Polarsteps payloads. TTL: 6 hours
  for ongoing trips, 30 days for finished trips. Bypass with `--no-cache`,
  refresh with `--refresh`.
- **`audio/<voice>/<model-id>-ndecsteps<N>/<chunk-hash>-<voice-hash>-<lang>.wav`**
  — per-chunk PCM segments. Tied to the model version + decoding
  parameters, so a model upgrade invalidates the cache automatically.
  Bypass with `--no-tts-cache`.

The audio cache lets you re-encode an entire trip into MP3 in seconds
once the chunks are synthesized: in our reference run, the first WAV
pass took ~2 hours of GPU time, the MP3 re-encode 39 seconds.

---

## Text normalization

Polarsteps text is cleaned before being sent to Voxtral. The cleaner
applies (in order):

1. Strip emojis and URLs.
2. **List bullets** (`- Option 1`) become sentence boundaries (`. Option 1`)
   so Voxtral does not phonetize the dash as the letter "n".
3. **Inline dash separators** (`BARILOCHE - ZAPALA`) become commas.
   Composés français with attached hyphens (`rendez-vous`, `semble-t-il`)
   are preserved.
4. **All-caps words** of 4+ characters are title-cased (`BARILOCHE` →
   `Bariloche`, `JOUR` → `Jour`). Short acronyms (GR, TMB, PCT) survive.
5. **`Jour N`** is rewritten as the French ordinal (`Premier jour`,
   `Deuxième jour`, …, `Trentième jour`) to give Voxtral a fully
   lexicalised token at chunk boundaries.
6. Common abbreviations are expanded: `12 km` → `12 kilomètres`,
   `2h30` → `2 heures 30`, `15°C` → `15 degrés`, `80 km/h` →
   `80 kilomètres-heure`, `D+` → `dénivelé positif`, etc.
7. Punctuation cleanup (multiple `.` → ellipsis, etc.) and whitespace
   normalization (paragraph boundaries preserved for the chunker).

The same cleaner is applied to the step name before it reaches the
spoken intro.

---

## Architecture

The codebase follows a pragmatic Clean Architecture layout:

```
src/polarsteps_tts/
├── domain/              # Pure business logic, no external dependencies
│   ├── entities/        # Trip, Step, AudioSegment, NarrationScript, Voice
│   ├── ports/           # TripRepository, TextToSpeechEngine, …
│   ├── services/        # IntroGenerator, TextCleaner, TextChunker
│   ├── value_objects/   # TripId, Slug, SynthesisOptions
│   └── exceptions/      # DomainError hierarchy
├── application/         # Use cases (orchestration), depend only on domain
│   └── use_cases/       # FetchTrip, PrepareNarration, SynthesizeStep
├── infrastructure/      # Concrete adapters
│   ├── polarsteps/      # HTTP client, payload parser, cached repository
│   ├── tts/voxtral/     # Voxtral OpenAI-compatible HTTP adapter
│   ├── cache/           # JsonFileCache, WavFileAudioSegmentCache
│   └── storage/         # Atomic file writes
└── presentation/        # CLI (typer + rich)
    ├── cli/             # Command definitions
    └── handlers/        # CLI → use case glue, audio file writing
```

Dependency rule: `presentation → application → domain` and
`infrastructure → application → domain`. The domain layer has no
external dependencies and is pure Python.

---

## Development

```bash
# Run the test suite
pytest                          # ~320 tests, < 1 second

# With coverage
pytest --cov=src/polarsteps_tts --cov-report=term-missing

# Lint, format, type-check
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

Tests run entirely against mocked HTTP and local fixtures; they do not
require a Voxtral server or GPU.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Voxtral server unreachable at http://localhost:8091` | Server not running | `./scripts/serve-voxtral.sh` |
| Server crashes at boot with `notify_kv_transfer_request_rejected` | `vllm` and `vllm-omni` versions mismatched | `pip install "vllm==0.20.2" "vllm-omni==0.20.0"` |
| Trip fetch fails with `Trip not found` | Trip ID does not exist or trip is private | Verify the URL in your browser |
| Trip fetch returns 0 steps | Polarsteps API quirk on some `polarsteps-api-version` headers | Already worked around in `infrastructure/polarsteps/http_client.py` |
| Whole-trip synthesis takes hours | First run synthesizes every chunk; expect ~2× real-time on a 24 GB GPU | Subsequent runs hit the audio cache (≈ 1 minute for 30+ steps) |

---

## License

The Python code in this repository is licensed under the **MIT License**.

⚠️ **Voxtral-4B-TTS-2603** itself is licensed under
**[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**
(non-commercial use only). Any audio you generate with it inherits that
constraint — fine for personal travel journals, not for commercial
distribution.

---

## Acknowledgements

- [Polarsteps](https://www.polarsteps.com/) — for the public trips API.
- [Mistral AI](https://mistral.ai/) — for releasing Voxtral.
- [vLLM-Omni](https://github.com/vllm-project/vllm-omni) — for the
  multimodal serving infrastructure.
