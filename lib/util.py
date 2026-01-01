import os


class util:
    @staticmethod
    def save_transcript_by_chapter(chapters_in_book, chapter_dir):
        chapter_count = len(chapters_in_book)
        number_width = max(1, len(str(chapter_count)))
        for chapter_index, chapter_sentences in enumerate(chapters_in_book, 1):
            chapter_filename = f"chapter_{chapter_index:0{number_width}d}.txt"
            chapter_path = os.path.join(chapter_dir, chapter_filename)
            with open(chapter_path, "w", encoding="utf-8") as chapter_file:
                chapter_file.write("\n".join(chapter_sentences))
        return chapter_count
