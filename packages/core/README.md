# OSI Core

Hub-and-spoke translator for metric definitions.

## What is OSI?

OSI (Open Semantic Interchange) is an open specification for defining and exchanging metric definitions. See the [OSI core spec](https://github.com/open-semantic-interchange/OSI/tree/main/core-spec) and [OSI converters](https://github.com/open-semantic-interchange/OSI/blob/main/converters/).

## Installation

```bash
pip install semetric-core
```

## Usage

Validate an OSI metric file:
```bash
osi-core validate metrics.yaml
```

Translate between formats:
```bash
osi-core translate metrics.yaml --from osi --to metricflow
```

Diff two metric files:
```bash
osi-core diff old.yaml new.yaml
```

## Supported Formats

- **OSI** (Open Semantic Interchange) — YAML
- **MetricFlow** (planned)
- **Snowflake** (planned)

## Development

```bash
uv sync
uv run pytest
```