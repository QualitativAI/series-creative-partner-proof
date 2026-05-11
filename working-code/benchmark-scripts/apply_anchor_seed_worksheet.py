#!/usr/bin/env python3
"""Parse completed anchor_seed worksheet, append final_eval rows, move promoted anchors, embed them.

Operator script for BRAIN_INTERVIEW_PROMPT.md. It is intentionally conservative:
- pre-eval rows come from manifest.draft.jsonl so brain_initial_* fields are preserved exactly
- worksheet fields are parsed from manifest.draft.md
- final_eval rows are appended only via validate_eval.py --append-jsonl
- holdout_benchmark rows are never embedded
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/workspace/series-vault')
SCRIPTS = ROOT / 'benchmark/scripts'
ANCHORS = ROOT / 'benchmark/anchors'
DRAFT_MD = ANCHORS / 'manifest.draft.md'
DRAFT_JSONL = ANCHORS / 'manifest.draft.jsonl'
FINAL_LOG = ROOT / 'benchmark/logs/final_eval_history.jsonl'
TMP = ROOT / 'benchmark/tmp/final_eval_anchor_seed'
SUMMARY_PATH = ROOT / 'benchmark/tmp/final_eval_anchor_seed_summary.json'
FINAL_RECORDS_JSONL = ROOT / 'benchmark/tmp/final_eval_anchor_seed_records.jsonl'
MANIFEST = ANCHORS / 'manifest.json'

LABELS = {'none', 'gold', 'anti', 'aspirational'}
WORLD_STATES = {'flourishing','sacred','broken','corrupted','abandoned','harsh','neutral','dna-core'}
TONES = {'hopeful','awe-filled','mournful','eerie','tense','oppressive','still','neutral'}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_worksheet() -> dict[str, dict]:
    text = DRAFT_MD.read_text()
    sections = re.split(r'(?m)^## ', text)[1:]
    parsed = {}
    for sec in sections:
        lines = sec.splitlines()
        filename = lines[0].strip()
        image_id_m = re.search(r'Image ID:\s*`([^`]+)`', sec)
        if not image_id_m:
            raise ValueError(f'{filename}: missing Image ID')
        image_id = image_id_m.group(1)

        def grab_until(label: str, next_labels: list[str]) -> str:
            # Match text after label until one of next labels or Brain baseline section.
            alternatives = '|'.join(re.escape(x) for x in next_labels + ['Brain baseline prediction:'])
            pat = re.compile(re.escape(label) + r'\s*(.*?)(?=\n(?:' + alternatives + r')|\Z)', re.S)
            m = pat.search(sec)
            return m.group(1).strip() if m else ''

        final_label = grab_until('Aaron final label:', ['Aaron score 0-10:', 'Aaron reason / why this label is right:', 'Aaron response to Brain, optional:']).strip()
        final_label = final_label.splitlines()[0].strip().lower() if final_label else ''
        score_raw = grab_until('Aaron score 0-10:', ['Aaron reason / why this label is right:', 'Aaron response to Brain, optional:']).strip()
        score_raw = score_raw.splitlines()[0].strip() if score_raw else ''
        reason = grab_until('Aaron reason / why this label is right:', ['Aaron response to Brain, optional:'])
        response = grab_until('Aaron response to Brain, optional:', [])
        # Remove placeholder blockquote-only lines but preserve Aaron's prose/newlines.
        def clean_block(s: str) -> str:
            out = []
            for line in s.splitlines():
                if line.strip() == '>':
                    continue
                # Keep quoted content if Aaron typed after >
                if line.lstrip().startswith('>'):
                    line = line.lstrip()[1:].lstrip()
                out.append(line.rstrip())
            return '\n'.join(out).strip()
        reason = clean_block(reason)
        response = clean_block(response)
        if final_label not in LABELS:
            raise ValueError(f'{filename}: final label {final_label!r} not one of {sorted(LABELS)}')
        try:
            score = int(score_raw)
        except Exception as e:
            raise ValueError(f'{filename}: invalid score {score_raw!r}') from e
        if not (0 <= score <= 10):
            raise ValueError(f'{filename}: score out of range {score}')
        if not reason:
            raise ValueError(f'{filename}: missing Aaron reason')
        parsed[image_id] = {
            'filename': filename,
            'image_id': image_id,
            'aaron_final_label_raw': final_label,
            'aaron_score': score,
            'aaron_reason': reason,
            'aaron_response': response,
        }
    return parsed


def load_preevals() -> list[dict]:
    rows = [json.loads(line) for line in DRAFT_JSONL.read_text().splitlines() if line.strip()]
    ids = [r['image_id'] for r in rows]
    if len(ids) != len(set(ids)):
        dupes = [x for x, n in Counter(ids).items() if n > 1]
        raise ValueError(f'duplicate image_ids in draft jsonl: {dupes}')
    return rows


def load_existing_final_rows(session_id: str) -> dict[str, dict]:
    existing = {}
    if not FINAL_LOG.exists():
        return existing
    for line in FINAL_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('session_id') == session_id and r.get('event_type') == 'final_eval':
            existing[r.get('image_id')] = r
    return existing


def manifest_anchor_ids() -> set[str]:
    if not MANIFEST.exists():
        return set()
    try:
        data = json.loads(MANIFEST.read_text())
    except Exception:
        return set()
    anchors = data.get('anchors', {})
    return set(anchors.keys()) if isinstance(anchors, dict) else set()


def infer_world_tone(pre: dict, reason: str) -> tuple[str, str]:
    # Aaron did not provide explicit locked world/tone fields in this worksheet.
    # Preserve Brain's locked-vocab state/tone unless Aaron's prose clearly names a locked vocab value.
    low = reason.lower()
    world = pre.get('brain_initial_world_state') if pre.get('brain_initial_world_state') in WORLD_STATES else 'neutral'
    tone = pre.get('brain_initial_tone') if pre.get('brain_initial_tone') in TONES else 'neutral'
    for w in WORLD_STATES:
        if re.search(r'\b' + re.escape(w) + r'\b', low):
            world = w
            break
    for t in TONES:
        if re.search(r'\b' + re.escape(t) + r'\b', low):
            tone = t
            break
    return world, tone


def quality_from_label_score(label: str, score: int) -> str:
    if label == 'anti':
        return 'bad'
    if label == 'aspirational':
        return 'aspirational'
    if label == 'gold':
        return 'approved' if score >= 9 else 'great'
    # none: preserve value as non-anchor taste data from score.
    if score <= 3:
        return 'bad'
    if score <= 6:
        return 'okay'
    if score == 7:
        return 'great'
    return 'approved'


def failure_from_label_quality(label: str, quality: str, reason: str):
    low = reason.lower()
    if quality in {'great','approved','aspirational','canon'}:
        return None
    if 'execution' in low or 'artifact' in low or 'hands' in low or 'anatomy' in low:
        return 'execution'
    if 'partial' in low or 'some' in low or 'but' in low:
        return 'partial' if label != 'anti' else 'concept'
    if label == 'anti' or quality == 'bad':
        return 'concept'
    return 'partial'


def tags_from_feedback(label: str, reason: str) -> str:
    low = reason.lower()
    tags = []
    def add(cond, tag):
        if cond and tag not in tags:
            tags.append(tag)
    add(label == 'anti', 'feels-grafted')
    add(label == 'gold', 'feels-native')
    add(label == 'aspirational', 'resonance-strong')
    add('anime' in low or 'animated' in low, 'reading-anime')
    add('real world' in low or 'modern' in low, 'too-real-world')
    add('lighting' in low or 'light' in low, 'lighting-good' if any(w in low for w in ['good','nice','gorgeous','beautiful','love']) else 'lighting-issue')
    add('composition' in low or 'framing' in low or 'depth' in low, 'composition-strong')
    add('detail' in low or 'detailed' in low or 'texture' in low, 'materiality-tactile')
    add('realistic' in low or 'realism' in low, 'realism-working')
    add('style' in low or 'aesthetic' in low, 'style-signal')
    add('beautiful' in low or 'gorgeous' in low, 'beauty-present')
    add('generic' in low, 'reading-generic-fantasy')
    add('color' in low or 'palette' in low, 'palette-signal')
    return ', '.join(tags[:10])


def feedback_text(reason: str, response: str) -> str:
    if response:
        return f"Aaron reason / why this label is right:\n{reason}\n\nAaron response to Brain, optional:\n{response}"
    return reason


def build_final_record(pre: dict, parsed: dict, moved_source_path: str | None = None) -> dict:
    label = parsed['aaron_final_label_raw']
    score = parsed['aaron_score']
    reason = parsed['aaron_reason']
    response = parsed['aaron_response']
    quality = quality_from_label_score(label, score)
    world, tone = infer_world_tone(pre, reason + '\n' + response)
    failure = failure_from_label_quality(label, quality, reason + '\n' + response)
    now = utc_now()
    rec = dict(pre)  # preserves Group A + Group B brain_initial_* exactly
    rec.update({
        'event_type': 'final_eval',
        'review_status': 'confirmed',
        'event_timestamp': now,
        'final_eval_timestamp': now,
        'source_path': moved_source_path or pre['source_path'],
        'aaron_score': score,
        'quality_tier': quality,
        'world_state': world,
        'tone': tone,
        'fits_current_scene': False if label == 'aspirational' else ('n-a' if label in {'anti','none'} else True),
        'failure_mode': failure,
        'feedback_tags': tags_from_feedback(label, reason + '\n' + response),
        'feedback_text': feedback_text(reason, response),
        'anchor_promotion': label,
        'canon_candidate': False,
        'final_notes': reason if not response else f"{reason}\n\nAaron response to Brain: {response}",
    })
    return rec


def validate_append(record: dict, stem: str) -> tuple[str, dict]:
    TMP.mkdir(parents=True, exist_ok=True)
    fp = TMP / f'{stem}.json'
    fp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    p = subprocess.run([
        sys.executable, str(SCRIPTS / 'validate_eval.py'), '--mode', 'final_eval',
        '--file', str(fp), '--append-jsonl', str(FINAL_LOG)
    ], cwd=str(ROOT), text=True, capture_output=True)
    out = p.stdout.strip()
    try:
        result = json.loads(out)
    except Exception as e:
        raise RuntimeError(f'validate_eval emitted non-json for {stem}: rc={p.returncode}\nSTDOUT={out}\nSTDERR={p.stderr}') from e
    if p.returncode != 0 or not result.get('ok'):
        raise RuntimeError(f'final_eval validation/append failed for {stem}:\n{json.dumps(result, indent=2)}\nSTDERR={p.stderr}')
    return result.get('append', {}).get('status', 'unknown'), result


def embed_record(record: dict, stem: str) -> tuple[bool, dict]:
    fp = TMP / f'{stem}.json'
    p = subprocess.run([
        sys.executable, str(SCRIPTS / 'embed_anchors.py'), '--record-file', str(fp)
    ], cwd=str(ROOT), text=True, capture_output=True)
    out = p.stdout.strip()
    try:
        result = json.loads(out)
    except Exception as e:
        result = {'ok': False, 'stage': 'output_parse', 'error': str(e), 'stdout': out, 'stderr': p.stderr, 'returncode': p.returncode}
    return p.returncode == 0 and result.get('ok') and not result.get('skipped'), result


def visual_anchor_count() -> int | None:
    code = """
import chromadb
c=chromadb.PersistentClient(path='/workspace/series-vault/benchmark/chroma_data')
col=c.get_or_create_collection(name='visual_anchors')
print(col.count())
"""
    p = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True, cwd=str(ROOT))
    if p.returncode != 0:
        return None
    return int(p.stdout.strip())


def main():
    parsed = parse_worksheet()
    preevals = load_preevals()
    if len(parsed) != len(preevals):
        raise ValueError(f'worksheet sections {len(parsed)} != draft jsonl rows {len(preevals)}')
    parsed_ids = set(parsed)
    pre_ids = {r['image_id'] for r in preevals}
    if parsed_ids != pre_ids:
        raise ValueError(f'worksheet/pre_eval image_id mismatch: only_md={sorted(parsed_ids-pre_ids)} only_jsonl={sorted(pre_ids-parsed_ids)}')

    session_id = preevals[0]['session_id'] if preevals else None
    existing_final = load_existing_final_rows(session_id)
    already_in_manifest = manifest_anchor_ids()

    summary = {
        'final_eval': {'appended': 0, 'skipped_duplicate': 0, 'other': 0},
        'moved_by_folder': {'gold': [], 'anti': [], 'aspirational': []},
        'already_moved_by_folder': {'gold': [], 'anti': [], 'aspirational': []},
        'embeds': {'attempted': 0, 'succeeded': 0, 'failed': 0, 'skipped_already_in_manifest': 0, 'results': []},
        'holdout_embedded': False,
        'records': [],
    }
    final_records = []

    for pre in preevals:
        if pre.get('image_origin') == 'holdout_benchmark':
            raise ValueError(f"Refusing to process holdout_benchmark in anchor seed worksheet: {pre['image_id']}")
        p = parsed[pre['image_id']]
        label = p['aaron_final_label_raw']
        source_path = Path(pre['source_path'])
        moved_path = None
        # Per BRAIN_INTERVIEW_PROMPT.md, promoted anchors must be moved before final validation/logging
        # so final_eval source_path, manifest, and embed_ready validation align.
        if label in {'gold', 'anti', 'aspirational'}:
            dest_dir = ANCHORS / label
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / pre['filename']
            if source_path.exists():
                if dest.exists():
                    # If already moved from a previous attempt, ensure same content hash by leaving it in place.
                    raise FileExistsError(f'destination already exists while source still exists: {dest}')
                shutil.move(str(source_path), str(dest))
                summary['moved_by_folder'][label].append(str(dest))
            elif dest.exists():
                # retry-safe: file was already moved in an earlier interrupted run
                summary['already_moved_by_folder'][label].append(str(dest))
            else:
                raise FileNotFoundError(f'neither source nor destination exists for promoted image {pre["filename"]}: {source_path} / {dest}')
            moved_path = str(dest)

        stem = Path(pre['filename']).stem
        if pre['image_id'] in existing_final:
            rec = existing_final[pre['image_id']]
            status = 'skipped_duplicate'
        else:
            rec = build_final_record(pre, p, moved_source_path=moved_path)
            status, val_result = validate_append(rec, stem)
        if status in summary['final_eval']:
            summary['final_eval'][status] += 1
        else:
            summary['final_eval']['other'] += 1
        final_records.append(rec)
        summary['records'].append({'filename': pre['filename'], 'image_id': pre['image_id'], 'anchor_promotion': label, 'append_status': status})

        if rec['anchor_promotion'] in {'gold','anti','aspirational'} and rec.get('image_origin') != 'holdout_benchmark':
            if rec['image_id'] in already_in_manifest:
                summary['embeds']['skipped_already_in_manifest'] += 1
            else:
                summary['embeds']['attempted'] += 1
                ok, er = embed_record(rec, stem)
                er_short = {'filename': pre['filename'], 'image_id': pre['image_id'], 'ok': bool(ok), 'result': er}
                summary['embeds']['results'].append(er_short)
                if ok:
                    summary['embeds']['succeeded'] += 1
                    already_in_manifest.add(rec['image_id'])
                else:
                    summary['embeds']['failed'] += 1
        elif rec.get('image_origin') == 'holdout_benchmark':
            summary['holdout_embedded'] = True

    FINAL_RECORDS_JSONL.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in final_records))
    summary['visual_anchors_count'] = visual_anchor_count()
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if summary['embeds']['failed']:
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}', file=sys.stderr)
        sys.exit(1)
