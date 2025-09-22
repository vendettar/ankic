# 🎯 Modern Anki Vocabulary Importer

A powerful, modern vocabulary importer for Anki with enhanced features, dependency injection architecture, and comprehensive error handling.

## ✨ Features

- **🏗️ Modern Architecture**: Dependency injection, interfaces, and factory patterns
- **⚡ Enhanced Performance**: Multi-layer caching (memory + disk) with LRU eviction
- **🛡️ Robust Error Handling**: Structured exceptions with detailed context
- **📊 Detailed Reporting**: Comprehensive processing statistics and results
- **🔧 Flexible Configuration**: Environment variable based configuration
- **🎵 Audio Support**: Automatic pronunciation download from multiple sources
- **📱 Beautiful Cards**: Modern, responsive card templates

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```bash
# Process individual words
ankic hello world example

# Process words from .txt files (auto-detected by suffix) 
ankic my_words.txt

# Mix words and files together
ankic word1 word2 my_words.txt more_words.txt

# Use custom deck
ankic --deck "MyVocab" word1 word2 my_words.txt

# Force update existing cards
ankic --force-update existing_word
```

### Advanced Options

```bash
# Skip audio download
ankic --no-audio word1 word2

# Custom processing delay
ankic --interval 2.0 word1 word2

# Show statistics
ankic --stats word1 word2 my_words.txt

# Clear cache (all or specific words) before processing
ankic --clear-cache                 # clear all cache
ankic --clear-cache word1 word2     # clear only specific words

# Show cache statistics
ankic --cache-stats

# List available card themes
ankic --list-themes
```

## 🎨 Card Themes

You can choose a built‑in visual theme for the generated Anki cards. Themes are discovered dynamically from `anki_connector/templates/themes/*`.

- Currently available in this repo: `dark, vapor, neon`
- Usage examples:
  - `ankic -t dark word1 word2`
  - `ankic -t dark words.txt`
  - List themes: `ankic --list-themes`

Implementation notes:
- Themes are implemented with a Jinja2 template engine for the card Front/Back/CSS.
- We keep Anki’s placeholders intact (e.g., `{{Word}}`) by using custom Jinja delimiters `[[ ... ]]` internally.
- Theme files live inside the package at `anki_connector/templates/themes/<theme>/`.

## ⚙️ Configuration

Create a `.env` file for custom configuration:

```env
# Anki Settings
ANKI__URL=http://localhost:8765
ANKI__DECK_NAME=MyVocabulary
ANKI__MODEL_NAME=MyVocabModel

# Audio Settings
AUDIO__DIR=my_audio
AUDIO__DELAY=1.0
MAX_CONCURRENT_DOWNLOADS=3

# Cache Settings
CACHE__DIR=.cache
CACHE__TTL_DAYS=30
CACHE__MAX_SIZE_MB=100

# Logging
LOG_LEVEL=INFO
```

## 📊 Processing Results

The tool provides detailed processing feedback:

```
📊 PROCESSING SUMMARY
=====================================
Total words processed: 10
✅ Successful: 8
❌ Failed: 1
⏭️ Skipped: 1
📈 Success rate: 80.0%

❌ Failed words:
  - invalidword: Word not found in vocabulary sources

⏭️ Skipped words:
  - existing: Card already exists
```

## 🏗️ Architecture

The application uses modern software engineering patterns:

- **Dependency Injection**: All components are loosely coupled and testable
- **Interface Segregation**: Clear contracts between components
- **Factory Pattern**: Easy instantiation and configuration
- **Layered Caching**: Memory + disk caching for optimal performance
- **Structured Exceptions**: Detailed error context and handling

## 🐛 Troubleshooting

### Debug Mode

```bash
ankic --debug word1 word2
```

### Check Configuration

```python
from anki_connector.config.settings import settings
print(settings.dict())
```

### Cache Issues

```bash
# Clear cache
ankic --clear-cache

# Check cache stats
ankic --cache-stats
```

## 📈 Performance

- **Cache Hit Rate**: Typically 80-90% for repeated runs
- **Memory Usage**: Efficient with LRU eviction
- **Processing Speed**: ~2-3 words/second (network dependent)
- **Storage**: Compressed disk cache with size limits

## 🤝 Contributing

The modern architecture makes contributions easier:

1. **Clear Interfaces**: Implement specific interfaces for new features
2. **Dependency Injection**: Easy to test and replace components
3. **Type Safety**: Pydantic models catch errors early
4. **Error Handling**: Consistent error reporting

## 📝 License


## ✅ Quality Checks

This project includes simple make targets to run tests and quality gates. Ensure dev dependencies are installed (via `uv sync --extra dev`).

Common tasks:

```
# Run unit tests
make test

# Type checks (mypy)
make type

# Lint (ruff)
make lint

# Format code (black)
make fmt

# Full quality gate: tests + mypy + ruff + black --check
make qa

# Alias for CI-quality gate
make ci
```

The Makefile uses `uv run` to execute tools inside your uv-managed environment.

MIT License - see LICENSE file for details.

---

**Note**: This is version 2.0 with completely rewritten architecture for better maintainability, performance, and extensibility.
