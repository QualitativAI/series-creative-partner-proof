#!/usr/bin/env python3
"""Run blind pre-eval for all anchor seed images in inbox.

This is an operator helper for the BRAIN_INTERVIEW_PROMPT workflow.
It calls describe_image.py --no-log, appends perception and pre_eval rows via
validate_eval.py --append-jsonl, and writes manifest.draft.md/jsonl.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/workspace/series-vault')
INBOX = ROOT / 'benchmark/anchors/inbox'
SCRIPTS = ROOT / 'benchmark/scripts'
LOGS = ROOT / 'benchmark/logs'
DRAFT_MD = ROOT / 'benchmark/anchors/manifest.draft.md'
DRAFT_JSONL = ROOT / 'benchmark/anchors/manifest.draft.jsonl'
STATE_FILE = ROOT / 'benchmark/anchors/.anchor_seed_preeval_session_id'
TMP = ROOT / 'benchmark/tmp'
PERCEPTION_LOG = LOGS / 'perception_history.jsonl'
PREEVAL_LOG = LOGS / 'pre_eval_history.jsonl'
IMAGE_ORIGIN = 'anchor_seed'
CREATED_BY = 'midjourney'


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def run_json(cmd: list[str], allow_fail: bool = False) -> tuple[dict, int, str]:
    p = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    out = (p.stdout or '').strip()
    err = (p.stderr or '').strip()
    if p.returncode != 0 and not allow_fail:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    try:
        return json.loads(out), p.returncode, err
    except json.JSONDecodeError as e:
        raise RuntimeError(f"non-json output from {' '.join(cmd)}\nreturn={p.returncode}\nSTDOUT:\n{out}\nSTDERR:\n{err}") from e


def describe_with_retry(img: Path) -> dict:
    try:
        rec, _, _ = run_json([sys.executable, str(SCRIPTS / 'describe_image.py'), str(img), '--no-log'])
        return rec
    except Exception as first:
        print(f"describe_image default failed for {img.name}; retrying gemini-3.1-pro-preview: {first}", flush=True)
        rec, _, _ = run_json([
            sys.executable, str(SCRIPTS / 'describe_image.py'), str(img), '--no-log', '--model', 'gemini-3.1-pro-preview'
        ])
        return rec


def write_and_append(record: dict, mode: str, target: Path, stem: str) -> dict:
    TMP.mkdir(parents=True, exist_ok=True)
    fp = TMP / f'{stem}.json'
    fp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    result, code, err = run_json([
        sys.executable, str(SCRIPTS / 'validate_eval.py'), '--mode', mode,
        '--file', str(fp), '--append-jsonl', str(target)
    ], allow_fail=True)
    if code != 0 or not result.get('ok'):
        raise RuntimeError(f"validation/append failed for {stem}:\n{json.dumps(result, indent=2)}\nSTDERR:{err}")
    return result


def rank_from_score(score):
    if score is None:
        return None
    if score >= 0.82:
        return 'strong'
    if score >= 0.72:
        return 'promising'
    if score >= 0.62:
        return 'borderline'
    return 'likely-miss'


def pick_state(text: str) -> tuple[str, str]:
    t = text.lower()
    rules = [
        ('corrupted', ['corrupt', 'twisted', 'wrongness', 'sickly', 'demonic', 'spikes', 'black tendrils', 'red glow', 'toxic', 'polluted']),
        ('sacred', ['sacred', 'holy', 'shrine', 'temple', 'cathedral', 'altar', 'ritual', 'pilgrim', 'sanctuary', 'reverent', 'divine']),
        ('broken', ['ruin', 'ruined', 'broken', 'collapsed', 'decay', 'decayed', 'damaged', 'fractured', 'cracked', 'rubble']),
        ('abandoned', ['abandoned', 'empty', 'forgotten', 'overgrown', 'uninhabited', 'deserted', 'no human', 'lack of human', 'boarded']),
        ('harsh', ['harsh', 'wasteland', 'storm', 'snow', 'ice', 'desert', 'cliff', 'jagged', 'dangerous', 'bleak', 'hostile']),
        ('flourishing', ['flourishing', 'thriving', 'lush', 'verdant', 'prosperous', 'market', 'vibrant', 'blooming', 'alive']),
    ]
    for state, keys in rules:
        if any(k in t for k in keys):
            return state, 'high' if state in ['sacred','corrupted','harsh'] else 'medium'
    if any(k in t for k in ['old', 'layered', 'ancient', 'weathered', 'mythic']):
        return 'dna-core', 'medium'
    return 'neutral', 'low'


def pick_tone(text: str) -> tuple[str, str]:
    t = text.lower()
    rules = [
        ('oppressive', ['oppressive', 'crushing', 'heavy', 'claustrophobic', 'overwhelming', 'dark mass']),
        ('tense', ['tense', 'danger', 'threat', 'imminent', 'storm', 'dramatic conflict', 'precarious']),
        ('eerie', ['eerie', 'unsettling', 'wrongness', 'uncanny', 'haunting', 'ghostly', 'sickly', 'strange']),
        ('awe-filled', ['awe', 'vast', 'monumental', 'grand', 'towering', 'mythic', 'divine', 'majestic', 'scale']),
        ('mournful', ['mournful', 'loss', 'sorrow', 'melancholy', 'desolate', 'lonely', 'forgotten']),
        ('hopeful', ['hopeful', 'warm', 'sunrise', 'golden', 'light breaking', 'possibility', 'uplift']),
        ('still', ['still', 'quiet', 'calm', 'solitary', 'reflective', 'contemplative', 'peaceful', 'silent']),
    ]
    for tone, keys in rules:
        if any(k in t for k in keys):
            return tone, 'medium'
    return 'neutral', 'low'


def detect_tags(rec: dict, state: str, tone: str) -> str:
    text = ' '.join(str(rec.get(k,'')) for k in [
        'perception_subject','perception_composition','perception_atmosphere',
        'perception_notable_details','perception_spatial_layout','perception_possible_state_cues','perception_possible_tone_cues'
    ]).lower()
    tags = []
    def add(cond, tag):
        if cond and tag not in tags:
            tags.append(tag)
    add(any(k in text for k in ['weathered', 'stone', 'masonry', 'carved']), 'weathered-materiality-good')
    add(any(k in text for k in ['golden', 'amber', 'sunset', 'sunrise', 'low-angle light']), 'late-light-good')
    add(any(k in text for k in ['mist', 'fog', 'haze', 'atmospheric']), 'atmosphere-on-point')
    add(any(k in text for k in ['vast', 'towering', 'monumental', 'grand', 'distant', 'scale']), 'mythic-scale-locked')
    add(any(k in text for k in ['layer', 'foreground', 'midground', 'background', 'depth']), 'depth-layers-working')
    add(any(k in text for k in ['ruin', 'decay', 'cracked', 'overgrown', 'abandoned']), 'feels-native')
    add(state == 'sacred', 'sacred-convincing')
    add(state == 'corrupted', 'corruption-reads')
    add(tone in ['awe-filled','hopeful','mournful','still'], 'emotional-weight-present')
    add(any(k in text for k in ['generic', 'sterile', 'clean', 'perfect symmetry']), 'reading-generic-fantasy')
    return ', '.join(tags[:7])


def judge(rec: dict, score: dict) -> dict:
    text = ' '.join(str(rec.get(k,'')) for k in [
        'perception_subject','perception_composition','perception_atmosphere',
        'perception_notable_details','perception_possible_state_cues','perception_possible_tone_cues'
    ])
    low = text.lower()
    state, state_conf = pick_state(text)
    tone, tone_conf = pick_tone(text)
    tags = detect_tags(rec, state, tone)
    positives = sum(k in low for k in ['weathered','ancient','layered','grand','vast','mythic','golden','mist','overgrown','carved','quiet','atmospheric','monumental','detailed','warm glow','scale'])
    negatives = sum(k in low for k in ['generic','sterile','plastic','cartoon','distorted','artifact','muddy','random','modern'])
    if negatives >= 2:
        tier, failure, promo = 'bad', 'concept', 'anti'
    elif positives >= 5 and state in {'sacred','broken','abandoned','harsh','dna-core','flourishing','corrupted'}:
        tier, failure, promo = 'aspirational', None, 'aspirational'
    elif positives >= 3:
        tier, failure, promo = 'great', None, 'gold' if state in {'sacred','broken','abandoned','harsh','dna-core','corrupted'} else 'none'
    else:
        tier, failure, promo = 'okay', 'partial', 'none'
    # For blind seeds, be sparing with gold: aspirational is safer unless the image reads as a clear lesson.
    if promo == 'gold' and not any(k in low for k in ['sacred','shrine','temple','cathedral','monumental','mythic','weathered','ancient','ruin','corrupt','harsh']):
        promo = 'none'
    notes_parts = []
    notes_parts.append(f"Reads as {state} / {tone} from the perception report")
    if tags:
        notes_parts.append(f"with signals: {tags}")
    if tier in ['great','aspirational']:
        notes_parts.append("Truthful old-world atmosphere appears stronger than generic beauty; Aaron should verify whether it is truly native enough to promote.")
    elif tier == 'bad':
        notes_parts.append("Perception suggests a potentially false or generic visual family; useful only if Aaron agrees it is a clear not-this reference.")
    else:
        notes_parts.append("Serviceable or partially resonant, but not enough evidence for anchor promotion without Aaron's confirmation.")
    score_raw = score.get('brain_initial_score_raw') if score.get('ok') else None
    gold = score.get('brain_initial_gold_similarity') if score.get('ok') else None
    anti = score.get('brain_initial_anti_similarity') if score.get('ok') else None
    return {
        'brain_initial_score_raw': score_raw,
        'brain_initial_gold_similarity': gold,
        'brain_initial_anti_similarity': anti,
        'brain_initial_rank': rank_from_score(score_raw),
        'brain_initial_quality_tier': tier,
        'brain_initial_world_state': state,
        'brain_initial_tone': tone,
        'brain_initial_scene_fit': 'n-a',
        'brain_initial_failure_mode': failure,
        'brain_initial_tags': tags,
        'brain_initial_notes': ' '.join(notes_parts),
        'brain_initial_anchor_promotion_recommendation': promo,
        'brain_initial_canon_candidate': tier == 'approved',
        'brain_initial_confidence': {
            'quality_tier': 'medium',
            'world_state': state_conf,
            'tone': tone_conf,
            'scene_fit': 'high',
            'anchor_promotion': 'medium' if promo != 'none' else 'low',
            'failure_mode': 'medium' if failure else 'high',
        },
        'brain_initial_questions_or_flags': None if promo == 'none' else 'Confirm whether this is truly anchor-worthy rather than merely beautiful.'
    }


def md_escape(s):
    if s is None:
        return 'null'
    return str(s).replace('\n', ' ')


def worksheet_section(rec: dict) -> str:
    flags = rec.get('brain_initial_questions_or_flags')
    lines = [
        f"## {rec['filename']}",
        "",
        f"Image: `{rec['source_path']}`",
        f"Image ID: `{rec['image_id']}`",
        "",
        "Aaron final label:",
        "",
        "Aaron score 0-10:",
        "",
        "Aaron reason / why this label is right:",
        ">",
        "",
        "Aaron response to Brain, optional:",
        ">",
        "",
        "Brain baseline prediction:",
        f"- Promotion: `{rec['brain_initial_anchor_promotion_recommendation']}`",
        f"- Quality tier: `{rec['brain_initial_quality_tier']}`",
        f"- World state: `{rec['brain_initial_world_state']}`",
        f"- Tone: `{rec['brain_initial_tone']}`",
        f"- Scene fit: `{rec['brain_initial_scene_fit']}`",
        f"- Failure mode: `{md_escape(rec['brain_initial_failure_mode'])}`",
        f"- Tags: `{rec['brain_initial_tags']}`",
        f"- Notes: {md_escape(rec['brain_initial_notes'])}",
    ]
    if flags:
        lines.append(f"- Brain flags/questions: {md_escape(flags)}")
    lines.append("")
    return '\n'.join(lines)


def load_existing_preevals(session_id: str) -> dict[str, dict]:
    existing = {}
    if not PREEVAL_LOG.exists():
        return existing
    for line in PREEVAL_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('session_id') == session_id and r.get('event_type') == 'pre_eval':
            existing[r.get('filename')] = r
    return existing


def main():
    if STATE_FILE.exists():
        session_id = STATE_FILE.read_text().strip()
    else:
        session_id = utc_now()
        STATE_FILE.write_text(session_id + '\n')
    images = sorted([p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}])
    print(f"session_id={session_id}")
    print(f"images={len(images)}")
    existing = load_existing_preevals(session_id)
    records = []
    append_counts = {'perception_appended':0, 'perception_skipped':0, 'pre_eval_appended':0, 'pre_eval_skipped':0, 'pre_eval_reused':0}
    for idx, img in enumerate(images, start=1):
        if img.name in existing:
            records.append(existing[img.name])
            append_counts['pre_eval_reused'] += 1
            print(f"[{idx}/{len(images)}] reuse existing pre_eval {img.name}", flush=True)
            continue
        print(f"[{idx}/{len(images)}] perceive {img.name}", flush=True)
        rec = describe_with_retry(img)
        now = utc_now()
        rec.update({
            'session_id': session_id,
            'image_origin': IMAGE_ORIGIN,
            'created_by': CREATED_BY,
            'event_type': 'perception',
            'review_status': 'pending',
            # keep perception_timestamp from Gemini call; set event_timestamp to this batch append time
            'event_timestamp': now,
        })
        pr = write_and_append(rec, 'perception', PERCEPTION_LOG, f"perception_{img.stem}")
        status = pr.get('append',{}).get('status')
        append_counts['perception_appended' if status == 'appended' else 'perception_skipped'] += 1
        print(f"[{idx}/{len(images)}] score {img.name}", flush=True)
        score, _, _ = run_json([sys.executable, str(SCRIPTS / 'score.py'), str(img)], allow_fail=True)
        if score.get('ok') is False and score.get('stage') != 'anchor_pool':
            raise RuntimeError(f"score.py failed unexpectedly for {img}: {json.dumps(score, indent=2)}")
        evtime = utc_now()
        pre = dict(rec)
        pre.update(judge(rec, score))
        pre.update({
            'event_type': 'pre_eval',
            'review_status': 'pre_evaluated',
            'event_timestamp': evtime,
            'brain_initial_timestamp': evtime,
        })
        rr = write_and_append(pre, 'pre_eval', PREEVAL_LOG, f"pre_eval_{img.stem}")
        status = rr.get('append',{}).get('status')
        append_counts['pre_eval_appended' if status == 'appended' else 'pre_eval_skipped'] += 1
        records.append(pre)
        print(f"[{idx}/{len(images)}] {img.name} -> {pre['brain_initial_quality_tier']} / {pre['brain_initial_world_state']} / {pre['brain_initial_tone']} / {pre['brain_initial_anchor_promotion_recommendation']}", flush=True)

    DRAFT_JSONL.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    md_header = [
        '# Anchor seed blind pre-eval worksheet',
        '',
        f'Session ID: `{session_id}`',
        f'Image origin: `{IMAGE_ORIGIN}`',
        f'Created by: `{CREATED_BY}`',
        f'Images: {len(records)}',
        '',
        'Fill in the Aaron fields under each image, then confirm in chat. Brain will not embed or move files until confirmation.',
        '',
    ]
    DRAFT_MD.write_text('\n'.join(md_header) + '\n'.join(worksheet_section(r) for r in records))
    p = subprocess.run([
        sys.executable, str(SCRIPTS / 'validate_eval.py'), '--mode', 'pre_eval', '--jsonl', str(DRAFT_JSONL)
    ], cwd=str(ROOT), text=True, capture_output=True)
    validation_out = (p.stdout or '').strip()
    validation_err = (p.stderr or '').strip()
    (TMP / 'manifest_draft_validation.stdout.jsonl').write_text(validation_out + ('\n' if validation_out else ''))
    if validation_err:
        (TMP / 'manifest_draft_validation.stderr.txt').write_text(validation_err + '\n')
    if p.returncode != 0:
        raise RuntimeError(f"draft JSONL validation failed; stdout saved to {TMP / 'manifest_draft_validation.stdout.jsonl'}\n{validation_out}\nSTDERR:\n{validation_err}")
    summary = {
        'ok': True,
        'session_id': session_id,
        'images': len(records),
        'draft_md': str(DRAFT_MD),
        'draft_jsonl': str(DRAFT_JSONL),
        'validation_stdout': str(TMP / 'manifest_draft_validation.stdout.jsonl'),
        **append_counts,
    }
    print('SUMMARY ' + json.dumps(summary, sort_keys=True), flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
