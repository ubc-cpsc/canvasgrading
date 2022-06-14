import canvas
from collections.abc import Callable
from typing import Any, Optional, Union
import argparse
import re
import sys

# TODO: help users with creating regular expressions (e.g., have a mode that displays the regexes and takes a test string to act on but doesn't act on Canvas?)
# TODO: make optionally interactive with confirmation of changes (via diffing?)
# TODO: test _html versus regular versions of comment fields; test madness about field names changing (see QuizQuestion update and Jonatan's original code for this)
# TODO: carefully publish quizzes that were already published beforehand OR have an option to do this? (See: https://community.canvaslms.com/t5/Question-Forum/Saving-Quizzes-w-API/td-p/226406); beware of publishing previously unpublished quizzes, of publishing a quiz in its update but BEFORE the questions are updated (??), and the like.


class BetterErrorParser(argparse.ArgumentParser):
    """ArgumentParser that shows the error and optionally help and then exits on errors."""

    def error(self, message, help=True):
        sys.stderr.write('error: %s\n' % message)
        if help:
            self.print_help()
        sys.exit(2)


def update_objects(objects: list[canvas.CourseSubObject],
                   type_name: str,
                   update_fn: Callable[[canvas.CourseSubObject], Any]) -> None:
    """Call update_fn on each element of objects (which should be of the given type)."""
    print("Processing %s objects" % type_name)
    for obj in objects:
        update_fn(obj)


def make_regex_repl_text_process(regex: str, repl: str) -> Callable[[Optional[str]], Optional[str]]:
    """Return a function to search for regex and replace with repl.

    The returned function just returns None if its argument is None.
    Otherwise, it globally searches for regex, making as many substitutions
    as possible with repl. If at least one substitution occurs, returns the
    resulting text. Else, returns None.
    """
    compiled_regex = re.compile(regex)

    def text_process(text: Optional[str]) -> Optional[str]:
        """Returns the result of processing text with a built-in regex/replacement.

        If text is None, returns None. If no substitution happens, returns None.
        Else, returns the substituted text.
        """
        if text is None:
            return None
        (new_text, count) = compiled_regex.subn(repl, text, count=0)
        return new_text if count > 0 else None
    return text_process

# text_process_fn takes text (as a string) and returns either None if no changes
# are to be made or a new block of text (as a string).
#
# text_fields is either a single string naming a text field to process or a list of
# such strings
#
# title_field is either None (for no title field) or a string naming the title field
# (only for logging). A field can be both title_field and one of the text_fields.


def make_update_text(text_process_fn: Callable[[Optional[str]], Optional[str]],
                     text_fields: Union[str, list[str]],
                     title_field: Optional[str] = None) -> Callable[[canvas.CourseSubObject], None]:
    """Return a function to update text fields in a CourseSubObject via text_process_fn.

    The returned function calls text_process_fn on each field indicated by
    text_fields (which is just the one if text_fields is a str), updating
    the value(s) of the field(s) with text_process_fn's return value whenever
    it returns a str. (If a field is missing or has a None value, text_process_fn
    receives None.)

    Updates may not occur after each call to text_process_fn (i.e., may be batched). 

    The title_field is used for logging if given. A field can be both a title_field
    and in text_fields.
    """
    text_fields = text_fields[:] if isinstance(
        text_fields, list) else[text_fields]

    def update_text(obj: canvas.CourseSubObject) -> None:
        """Calls the built-in text_process_fn on text fields in obj, updating as needed.

        The specific text_fields, title_field for logging, and the processing function
        are all created by an earlier call that generates this function.
        """
        print()
        print("---------------------------------------------------------------")
        if title_field:
            print("Processing object: %s" % obj[title_field])
        else:
            print("Processing next object")

        update_needed = False
        for text_field in text_fields:
            print("Processing text field: %s" % text_field)
            old_value = obj[text_field]
            new_value = text_process_fn(old_value)
            if new_value is None:
                print("No changes made.")
            else:
                update_needed = True
                obj[text_field] = new_value
                print("Changes made.")
                print("Old value:")
                print(old_value)
                print()
                print()
                print("New value:")
                print(new_value)
                print()
                print()

        if update_needed:
            print("Making update on Canvas...")
            obj.update()
            print("Update complete.")

        if title_field:
            print("Done processing object: %s" % obj[title_field])
        else:
            print("Done processing object")
    return update_text


parser = BetterErrorParser()
canvas.Canvas.add_arguments(parser)


parser.add_argument("-a", "--assignments",
                    help="Process assignments.", action="store_true")
parser.add_argument("-p", "--pages", help="Process pages.",
                    action="store_true")
parser.add_argument("-q", "--quizzes",
                    help="Process quizzes.", action="store_true")
parser.add_argument(
    "-A", "--all", help="Process all types (assignments, pages, and quizzes).", action="store_true")
parser.add_argument(
    "regex", help="The regular expression (using Python's re syntax) to search for.")
parser.add_argument(
    "repl", help="The replacement string (using Python's syntax from re.sub) with which to replace regex.")
args = parser.parse_args()

regex = args.regex
repl = args.repl

process_assns = args.assignments or args.all
process_pages = args.pages or args.all
process_quizzes = args.quizzes or args.all
if not (process_assns or process_pages or process_quizzes):
    parser.error(
        "You must use a flag to indicate processing of at least one type.")

std_text_process = make_regex_repl_text_process(regex, repl)
update_assn_fn = make_update_text(std_text_process, "description", "name")
update_page_fn = make_update_text(std_text_process, "body", "url")

update_quiz_text = make_update_text(std_text_process, "description", "title")


def update_quiz_and_questions(quiz: canvas.Quiz) -> None:
    """Perform regex search-and-replace on the quiz and its questions.

    Uses the script's global regex and replacement string.
    """
    print("Processing the quiz itself.")
    update_quiz_text(quiz)

    print("Fetching quiz questions from Canvas...")
    (quiz_question_dict, quiz_group_dict) = quiz.questions()
    quiz_questions = [canvas.QuizQuestion(
        qq, quiz) for qq in list(quiz_question_dict.values())]
    print("Done fetching quiz questions from Canvas.")

    # TODO: confirm html vs non-html variants are correct
    # TODO: account for answers!
    update_quiz_question = make_update_text(std_text_process,
                                            ["question_text",
                                             "correct_comments",
                                             "incorrect_comments",
                                             "neutral_comments",
                                             "correct_comments_html",
                                             "incorrect_comments_html",
                                             "neutral_comments_html"],
                                            "question_name")
    update_objects(quiz_questions, "quiz (%s) questions" %
                   quiz["title"], update_quiz_question)


update_quiz_fn = update_quiz_and_questions


canvasObj = canvas.Canvas(args=args)

print('Object types being processed: %s%s%s' %
      ("assignments " if process_assns else "",
       "pages " if process_pages else "",
       "quizzes " if process_quizzes else ""))


print('Reading data from Canvas...')
course = canvasObj.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))


if process_assns:
    print()
    print("--------------------------------------------------------------------------")
    print("Fetching assignments from Canvas...")
    assignments = course.assignments()
    print("Done fetching assignments from Canvas.")
    update_objects(assignments, "assignment", update_assn_fn)

if process_pages:
    print()
    print("--------------------------------------------------------------------------")
    print("Fetching pages from Canvas...")
    pages = course.pages()
    print("Done fetching pages from Canvas.")
    update_objects(pages, "page", update_page_fn)

if process_quizzes:
    print()
    print("--------------------------------------------------------------------------")
    print("Fetching quizzes from Canvas...")
    quizzes = course.quizzes()
    print("Done fetching quizzes from Canvas.")
    update_objects(quizzes, "quiz", update_quiz_fn)


# Note: for some reason, Course.assignments filters out "online_quiz" assignment types. Should it?? Are those "Quiz" instead?
