# canvasgrading

## quiz2pdf.py

This is a script that converts a Canvas quiz to a PDF suitable for
Gradescope. It receives 3-5 arguments:

1. A string used as prefix for the output files. Can also be used to
specify a different directory to store the data in.

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

Please submit any questions or comments to [jonatan@cs.ubc.ca]. Note
that there are some question types I haven't implemented yet since
they were not in my midterm, such as multiple dropdowns or multiple
answers, I'll update the script with those once I have a chance.