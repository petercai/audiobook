# Regex Explanation: Hard Sentence Splitting

This document explains the regular expression used in `sentence_splitter.py` for splitting paragraphs into sentences based on "hard" punctuation. It also details a bug found in the pattern construction.

## The Regex Pattern

```regex
(.*?(?:।|\.|\?|‽|…|？|!|॥|።|།|！|。|៕|፧|។|؟)—༎?…॥！፥,፦»、·：.¡໌‽།¿።؛。៕፣।ฯ";ໍ፧״។؟،？፡!；:፤，«)(?=\s|$)
```

## High-Level Goal

The intended purpose of this regex is to find and capture individual sentences from a larger block of text. It attempts to match text segments that end with a sentence-terminating punctuation mark, ensuring the split occurs at the end of a word.

## Component-by-Component Explanation

The pattern can be broken down into four main parts:

### Part 1: `(.*?)`
*   `(`...`)`: This is the main **capturing group**. The text matched here is returned as the result.
*   `.`: Matches any single character. With the `regex.S` (DOTALL) flag, this includes newlines.
*   `*?`: This is a **non-greedy quantifier**. It matches as few characters as possible while still allowing the rest of the pattern to match. This ensures the regex stops at the *first* sentence-ending punctuation, not the last one in the paragraph.

### Part 2: `(?:।|\.|\?|‽|…|？|!|॥|።|།|！|。|៕|፧|។|؟)`
*   `(?:...)`: A **non-capturing group**.
*   `|`: The "OR" operator.
*   Matches one of the specific "hard" punctuation marks (e.g., `.`, `?`, `!`, `。`, `॥`).

### Part 3 (The Bug): `—༎?…॥！፥,፦»、·：.¡໌‽།¿።؛。៕፣।ฯ";ໍ፧״។؟،？፡!；:፤，«`
*   **What it is:** This long sequence is treated by the regex engine as a **literal string**.
*   **The Bug:** In `sentence_splitter.py`, the regex is constructed via:
    ```python
    rf"(.*?(?:{_HARD_SPLIT}){''.join(punctuation_list_set)})(?=\s|$)"
    ```
    The code `{''.join(punctuation_list_set)}` incorrectly concatenates all known punctuation into a single string without placing them in a character class (like `[...]`) or an alternation group.
*   **Consequence:** The regex engine expects to find this *exact, jumbled sequence of characters* immediately following the hard punctuation mark. Since this sequence virtually never appears in natural text, the regex will fail to match.

### Part 4: `(?=\s|$)`
*   `(?=...)`: A **positive lookahead**. It checks the text following the current position without consuming it.
*   `\s`: Matches any whitespace character.
*   `$`: Matches the end of the string.
*   **Purpose:** Asserts that the sentence ends at a word boundary (followed by space) or the end of the text.

## Conclusion

The regular expression is designed to capture a sentence by matching text up to a hard punctuation mark. However, it is critically flawed due to the bug in Part 3. It requires the match to be followed by a long, specific, and nonsensical string of literal punctuation, rendering it non-functional for its intended purpose.

## The Fix

To fix the bug in `_HARD_PATTERN`, we need to convert the literal string concatenation of punctuation characters into a proper regex character class.

The original code `{''.join(punctuation_list_set)}` creates a literal sequence (e.g., `"!?,."`) that the regex expects to match exactly in that order. The fix involves:
1.  Using `re.escape` on each character to ensure special regex characters (like `.`, `?`, `-`) are treated literally.
2.  Wrapping the result in `[...]` to create a character class.
3.  Adding `*` to allow matching zero or more of these trailing punctuation characters.

### Corrected Code

```python
_HARD_PATTERN = re.compile(
    rf"(.*?(?:{_HARD_SPLIT})[{''.join(map(re.escape, punctuation_list_set))}]*)(?=\s|$)",
    re.DOTALL,
)
```

## Analysis of Punctuation Sets

### 1. Overlap between `punctuation_list_set` and `_HARD_SPLIT`

`punctuation_list_set` includes all characters in `punctuation_split_hard_set`. `punctuation_split_hard_set` is a subset of `punctuation_list_set`.

### 2. Handling Duplication

The overlap is intentional and handled correctly by the regex structure:
*   `(?:{_HARD_SPLIT})`: Matches **exactly one** hard punctuation character (the primary trigger).
*   `[{...}]*`: Matches **zero or more** of *any* punctuation characters (hard or soft) immediately following the trigger.

**Example:**
For the text "Is it finished?!":
*   `.*?` matches "Is it finished"
*   `(?:{_HARD_SPLIT})` matches "?"
*   `[{...}]*` matches "!"

The result is "Is it finished?!", which correctly keeps the trailing punctuation attached to the sentence.

### 3. Performance Impact

The fix uses efficient regex primitives:
*   Non-greedy match `.*?`
*   Alternation of literals `(?:...|...)`
*   Character class `[...]`

There is no significant negative performance impact; this is a standard and efficient way to handle tokenization with variable trailing punctuation.