# canvasgrading

## quiz2pdf.py

This is a script that converts a Canvas quiz to a PDF suitable for
Gradescope. It receives 3-6 arguments, in this order:

1. A string used as prefix for the output files. Can also be used to
specify a different directory to store the data in (e.g.,
`~/cs299/Final/FinalExam`).

2. The name of a classlist CSV file containing at least the columns
SNUM and ACCT. You can generate it on the department computers with a
command like:

    classlist <course_num> -T -f "%SN,%ACCT"

3. A text file containing a Canvas access token associated to your
account ([https://canvas.ubc.ca/profile/settings], see Approved
Integrations).

4. (optional) The ID of the course on Canvas. If you don't specify it,
the script lists all courses you have access to and asks for a
course. The ID can be obtained by looking at the URL on Canvas, it's
the number after 'courses/'.

5. (optional) The ID of the quiz to convert.  If you don't specify it,
the script lists all quizzes from the course you selected and asks for
a course. The ID can be obtained by looking at the URL on Canvas when
you open the quiz, it's the number after 'quizzes/'.

6. (optional) A comma-separated list of question IDs to include. If
not specified, all questions are included. The ID of the question can
be obtained by running this script with all questions (without this
argument), the number provided before the text of each question is the
question ID.

The script will connect to the Canvas API to get the latest responses
from Canvas itself. The program will generate a file
`XXX_template.html` and `XXX_template.html.pdf`, where `XXX` is the
string from the first argument; the PDF file can be used as a template
for a quiz on Gradescope. The script will also create a series of
files named `XXX_exams_YY.html` and `XXX_exams_YY.html.pdf`, where YY
is a counter; each file contains up to 20 exams, which can be uploaded
to Gradescope as exams.

The script also creates a file named `XXX_raw_answers.zip` containing
a file for each essay question in the quiz. For quizzes with multiple
attempts allowed, these files will be created for all attempts. This
file is named `answer_<QID>_<ACCT>_v<ATT>.html`, where `<QID>`,
`<ACCT>` and `<ATT>` are the question ID, student account and attempt
number, respectively. These can be useful in cases where either the
answer is too long to fit in a PDF page, or if the marker wants to
copy that answer to test it (e.g., in an IDE). Also, for all file
upload type questions, the uploads will be saved in the same file, in
a file named `answer_<QID>_<ACCT>_v<ATT>_<FN>`, where FN is the file
name originally used by the submitter.

The script supports all question types allowed in Canvas classic
quizzes, including text-only, essay, file upload, fill-in the blank
(or multiple blanks), multiple choice (including true/false and
multiple answers), multiple dropdowns, matching, numerical answers and
formula (calculated) questions. It also supports question groups, in
which case each question version is saved in a different page, and any
question submission that doesn't include a specific question will list
the answer as "NO SUBMISSION", with an explanation text. For file
upload questions, the answer will list the file names included in the
answer, which can be found in the raw answers file listed above. For
all other questions, the answer will be listed in the PDF itself. If
the question plus answer don't fit a single page, it will be
truncated, and you may find the answer in the raw answers file above.

Please submit any questions or comments to jonatan@cs.ubc.ca.