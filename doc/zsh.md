If you’re on macOS with `zsh`, the simplest way to list every `model.pth` in subfolders with human‑readable sizes (K/M/G) is to use `du -h` together with either `find` or zsh’s recursive globbing.

### Option 1 — Using `find` (portable)

```zsh
# From the directory you want to search:
find . -type f -name 'model.pth' -exec du -h {} +
```

*   `du -h` prints sizes in **K**, **M**, **G** (KiB/MiB/GiB style).
*   The `+` batches multiple files, making it faster than running `du` per file.

**Sort by size (largest first):**

```zsh
find . -type f -name 'model.pth' -exec du -h {} + | sort -h -r
```

> Note: If your macOS `sort` doesn’t support `-h`, install GNU coreutils (`brew install coreutils`) and use `gsort -h -r`.

***

### Option 2 — Using zsh recursive globbing (fast & clean)

```zsh
# Enable recursive globbing if not already:
setopt globstar

# List sizes in human-readable units
du -h **/model.pth(.N)
```

*   `**/model.pth` finds `model.pth` in all subfolders.
*   `(.N)` restricts to **normal files** and suppresses errors if none are found.
*   Output format: `SIZE<TAB>PATH`, where SIZE is in **K/M/G**.

**Sorted (largest first):**

```zsh
du -h **/model.pth(.N) | sort -h -r
```

***

### Option 3 — Show just the size and filename (neat columns)

```zsh
du -h **/model.pth(.N) | awk '{printf "%-8s %s\n", $1, $2}'
```

***

### Notes & Tips

*   Run these from the project root (or replace `.` with your base directory).
*   If filenames contain spaces, all the commands above handle them safely.
*   `ls -lh` shows human-readable sizes too, but it reports the *file size*, while `du -h` reports *disk usage*. For `.pth` files these are usually the same, but `du` is typically preferred for summaries and sorting.

Want me to wrap this into a reusable zsh function (e.g., `list_pth_sizes`) you can drop into your `~/.zshrc`?


Awesome — here’s a drop‑in **zsh function** you can add to your `~/.zshrc` to list all `model.pth` files under a directory (recursively) with their sizes in **human‑readable K/M/G** format, and sort/filter them as you like.

### 🔧 Function: `list_pth_sizes`

```zsh
# List sizes of all model.pth files under a directory, with sorting/filtering.
# Default directory is the current one.
# Options:
#   -d <dir>   Base directory to search (default: .)
#   -s <order> Sort order: asc|desc (default: desc)
#   -n <N>     Show only the top N entries (after sorting)
#   -F         Use file size (stat) instead of disk usage (du) [default: stat]
#   -U         Use disk usage (du -k), which accounts for filesystem blocks
#   -0         Show size in bytes instead of human-readable K/M/G
#
# Examples:
#   list_pth_sizes                     # current dir, desc
#   list_pth_sizes -d /data -s asc     # search /data, smallest first
#   list_pth_sizes -n 10               # top 10 largest
#   list_pth_sizes -U                  # use disk usage (du)
#   list_pth_sizes -0                  # raw bytes

function list_pth_sizes() {
  local dir="."
  local order="desc"
  local limit=""
  local use_du=0
  local raw_bytes=0

  while getopts "d:s:n:UF0h" opt; do
    case "$opt" in
      d) dir="$OPTARG" ;;
      s) order="$OPTARG" ;;
      n) limit="$OPTARG" ;;
      U) use_du=1 ;;
      F) use_du=0 ;;  # explicit file-size mode
      0) raw_bytes=1 ;;
      h)
        cat <<'USAGE'
Usage: list_pth_sizes [-d DIR] [-s asc|desc] [-n N] [-F|-U] [-0]
  -d DIR   Base directory to search (default: .)
  -s ORDER Sort order: asc|desc (default: desc)
  -n N     Show only top N after sorting
  -F       Use file size (stat) [default]
  -U       Use disk usage (du -k)
  -0       Print raw bytes instead of human-readable units
USAGE
        return 0
        ;;
      *) echo "Invalid option"; return 1 ;;
    esac
  done
  shift $((OPTIND - 1))

  # Ensure directory exists
  if [[ ! -d "$dir" ]]; then
    echo "Error: Directory not found: $dir" >&2
    return 1
  fi

  # Find files safely (handles spaces/newlines with -print0)
  # Use macOS-friendly tools: stat(1) with -f, du(1) with -k.
  local tmpfile
  tmpfile="$(mktemp -t pthsizes)"
  # shellcheck disable=SC2069 # zsh-specific
  if (( use_du )); then
    # Disk usage in KiB via du -k, then convert
    # Output to tmpfile as: <bytes> <path>
    find "$dir" -type f -name 'model.pth' -print0 \
      | xargs -0 -I{} du -k {} \
      | awk 'BEGIN{OFS=" "} {print $1*1024, $2}' > "$tmpfile"
  else
    # File size via stat -f "%N %z" (macOS)
    find "$dir" -type f -name 'model.pth' -print0 \
      | xargs -0 stat -f "%N %z" > "$tmpfile"
  fi

  # If no files were found
  if [[ ! -s "$tmpfile" ]]; then
    echo "No model.pth files found under: $dir"
    rm -f "$tmpfile"
    return 0
  fi

  # Sort numeric by size (2nd field), asc or desc
  if [[ "$order" == "asc" ]]; then
    sort -k2,2n "$tmpfile" -o "$tmpfile"
  else
    sort -k2,2nr "$tmpfile" -o "$tmpfile"
  fi

  # Apply limit if requested
  if [[ -n "$limit" ]]; then
    head -n "$limit" "$tmpfile" > "${tmpfile}.head"
    mv "${tmpfile}.head" "$tmpfile"
  fi

  # Print results with human-readable sizes unless -0 was set
  if (( raw_bytes )); then
    # bytes PATH
    awk 'BEGIN{OFS="\t"} {printf "%-12s %s\n", $2, $1}' \
      <(awk '{print $2, $1}' "$tmpfile")
  else
    # Humanize bytes to K/M/G/T (binary IEC-ish)
    awk '
      function humanize(bytes,   u, v) {
        u[0]="B"; u[1]="K"; u[2]="M"; u[3]="G"; u[4]="T"; u[5]="P";
        v = bytes + 0;
        i = 0;
        while (v >= 1024 && i < 5) { v /= 1024; i++ }
        # Use 1 decimal for K/M/G/T, none for B
        if (i == 0) return sprintf("%.0f%s", v, u[i]);
        else return sprintf("%.1f%s", v, u[i]);
      }
      {
        size=$2; path=$1;
        print sprintf("%-8s %s", humanize(size), path);
      }
    ' <(awk '{print $1" "$2}' "$tmpfile")
  fi

  rm -f "$tmpfile"
}
```

### 📌 How to install

1.  **Copy** the function into your `~/.zshrc` (or a file you source from it, e.g., `~/.zsh/functions.zsh`).
2.  **Reload** your shell:
    ```zsh
    source ~/.zshrc
    ```
3.  **Run** it from any project directory:
    ```zsh
    list_pth_sizes
    list_pth_sizes -d /path/to/models -s asc
    list_pth_sizes -n 10
    list_pth_sizes -U        # use filesystem disk usage
    list_pth_sizes -0        # show raw bytes
    ```

### 📝 Notes

*   By default this uses **file size** via `stat` (reliable and fast). Use `-U` if you prefer **disk usage** via `du`, which accounts for filesystem block allocation (can differ slightly from file size depending on sparse files or compression).
*   We avoid GNU‑specific flags so it works out of the box on macOS (no `numfmt`, no `sort -h`). Sorting is done numerically on bytes and we **humanize** after sorting.
*   Handles paths with spaces safely via `-print0` and `xargs -0`.

Want me to add **autocomplete** for the flags or allow a custom filename pattern (e.g., `-p '*.pth'`)?
