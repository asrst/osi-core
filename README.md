# osi-core

An OSI Native Metric Compiler/Converter.

## What is OSI?

OSI (Open Semantic Interchange) is an open specification for defining and exchanging metric definitions across tools and platforms. See the [OSI core spec](https://github.com/open-semantic-interchange/OSI/tree/main/core-spec) for the specification, and the [OSI converters](https://github.com/open-semantic-interchange/OSI/blob/main/converters/) for related converter implementations.

## What is osi-core?

osi-core is a hub-and-spoke translator for metric definitions. It reads metric files in one format and can translate them to another, making it easier to move metrics between systems.

Currently supported: **OSI** (YAML).

Planned: vendor converters such as **Snowflake**, **GoodData**, and others.

## Quick Start

```bash
pip install osi-core
```

```bash
osi-core validate metrics.yaml --format osi
osi-core translate metrics.yaml --from osi --to osi
osi-core diff old.yaml new.yaml
```

## Development

```bash
uv sync
uv run pytest
```

See [`docs/DEVELOPER.md`](docs/DEVELOPER.md) for more details.