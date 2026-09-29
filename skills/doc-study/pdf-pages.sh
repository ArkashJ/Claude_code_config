#!/usr/bin/env bash
# pdf-pages.sh <pdf> <first> <last> <outdir> [dpi=110]
# Render PNG + per-page layout text for a page range, then print a page -> title map.
#
# INCIDENT (Spot BEN-175, 2026-09-29): the 134-page ABA study keeps its data in CHARTS; text extraction was
# useless, so pages were rendered (pdftoppm -r 110) and READ AS IMAGES by parallel agents -- 152 chart readings,
# 51 of them carrying an ambiguity note. This is that step as one command: hand each agent a page range and
# the PNGs, and hand the title map to whoever assigns ranges. 110 dpi is the measured legibility/size trade;
# raise it (150) for small legend text -- the run report in SKILL.md says which pages needed it.
# Fail-closed: prints "rendered N/N pages" and exits 1 unless every requested PNG and txt exists and is non-empty.
set -euo pipefail
[ $# -ge 4 ] && [ $# -le 5 ] || { sed -n '2,2p' "$0" | sed 's/^# //' >&2; exit 2; }
pdf=$1 first=$2 last=$3 out=$4 dpi=${5:-110}
[ -f "$pdf" ] || { echo "pdf-pages: no such file: $pdf" >&2; exit 2; }
case $first$last in *[!0-9]*) echo "pdf-pages: first/last must be integers" >&2; exit 2;; esac
total=$(pdfinfo "$pdf" | awk '/^Pages:/ {print $2}')
[ -n "$total" ] || { echo "pdf-pages: pdfinfo gave no page count for $pdf" >&2; exit 1; }
if [ "$first" -lt 1 ] || [ "$last" -lt "$first" ] || [ "$last" -gt "$total" ]; then
  echo "pdf-pages: range $first-$last invalid for a $total-page PDF" >&2; exit 2
fi
mkdir -p "$out"
n=0 ok=0
for ((p = first; p <= last; p++)); do
  base=$(printf '%s/page-%03d' "$out" "$p")
  n=$((n + 1))
  pdftoppm -r "$dpi" -f "$p" -l "$p" -png -singlefile "$pdf" "$base"
  pdftotext -layout -f "$p" -l "$p" "$pdf" "$base.txt"
  if [ -s "$base.png" ] && [ -f "$base.txt" ]; then ok=$((ok + 1)); fi
  # title = first line with 3+ letters (chart pages often have none: "(no text layer)")
  title=$(awk 'NF && /[A-Za-z][A-Za-z][A-Za-z]/ {gsub(/^[ \t]+|[ \t]+$/, ""); print substr($0, 1, 70); exit}' "$base.txt")
  printf 'page %03d  %s\n' "$p" "${title:-(no text layer: read the image)}"
done
echo "rendered $ok/$n pages at ${dpi}dpi into $out"
[ "$ok" -eq "$n" ]
