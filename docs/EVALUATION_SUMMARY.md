# Evaluation Summary

The system includes a taste-memory workflow for helping the Brain learn Aaron's visual preferences from structured review.

## Holdout Check

A 31-item blind holdout check was used to test whether the taste-memory workflow improved the Brain's ability to predict Aaron's visual taste labels.

- Frozen baseline exact-label match score: `3/31`
- Post-workflow retest exact-label match score: `7/31`

This is not presented as a finished taste model. It is evidence that the workflow became measurable and improved after structured taste memory, feedback contracts, and review tooling were implemented.

## What Is Included

- Scoring and evaluation scripts in `working-code/benchmark-scripts/`
- Schema and methodology references in `source-of-truth/SCHEMA.md`
- Build-plan references for anchor handling, holdout checks, scoring, and validation in `build-plans/series-vault/`

## What Is Kept Out Of The Main Review Path

This compact proof repo does not include the full per-item holdout table or answer rows. The aggregate before/after result is included here, and the scripts/schema are included so the method is inspectable without turning the repo into a full evaluation archive.
