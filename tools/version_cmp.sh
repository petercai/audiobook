uv export --no-hashes --format requirements.txt \
  | grep -vE '^\s*#' \
  | sed -E '/^\s*$/d' \
  | sort \
  > ver-uv-export.txt


uv pip freeze \
  | sed -E 's/;.*$//' \
  | sed -E 's/\s+//g' \
  | sort \
  > ver-pip-freeze.txt

diff -u ver-pip-freeze.txt ver-uv-export.txt || true
