"""
@author: Carmel WENGA
"""
from openai import OpenAI
from settings import config, system_message

import argparse
import pandas as pd
import json

from tqdm import tqdm
tqdm.pandas()

parser = argparse.ArgumentParser()
parser.add_argument("input", help="Name of the input file")
parser.add_argument("output", help="Name of the output file.")

# Function to generate user prompt for the OpenAI API
def generate_user_prompt(question):
    """
    This function is user to build/generate the question and it context as the prompt

    :question (dataframe row) is a line of the source dataset with the following columns: 
        - "Question #","Statement","My Answer","Expected Answer","Answer Status","Comments","Categories","GCP Services or Tools","Concepts or Topics"
    """
    user_message = f"""
    \nQUESTION STATEMENT: {question["Statement"]}
    """
    # If an answer (Expected Answer) has been provided to the question, then add the answer in the prompt
    if question["Expected Answer"] != "#EMPTY#":
        user_message += f"\nANSWER: {question['Expected Answer']}"

    # If the question has already been categorized, add the initial categorization in the prompt
    if any([value != "#EMPTY#" for value in question[["Categories","GCP Services or Tools","Concepts or Topics"]].tolist()]):
        user_message += f"""\nINITIAL CATEGORIZATION: These are the categories that were initially set for the above question
        * **related_categories**: {question["Categories"]}
        * **related_technologies**: {question["GCP Services or Tools"]}
        * **related_skills**: {question["Concepts or Topics"]}
        """

    # If the question has a comment that can be useful as a context, add it in the prompt
    if question["Comments"] != "#EMPTY#":
        user_message += f"\nCOMMENTS: {question['Comments']}"

    return user_message

class QuestionCategorizer:

    def __init__(self, questions:pd.DataFrame, output_filename:str):
        self.openai_client = OpenAI(api_key=config.get("OPENAI_API_KEY"))
        self.questions = questions
        self.output_filename = output_filename

    def categorize_with_openai(self, question):
        # Call openai to apply categorization to a question
        user_message = generate_user_prompt(question)
        
        response = self.openai_client.chat.completions.create(
            model = 'gpt-4o',
            messages = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system_message
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_message
                        }
                    ]
                }
            ]
        )

        answer = response.choices[0].message.content
        return answer.replace("\n","").replace("```json","").replace("```","")

    def save_question_categorization(self, question):
        """
        Parses the generated answer JSON and updates the related_categories, related_technologies, and related_skills columns in the question.

        :question the question to categorize
        """
        # Call the categorize_with_openai function with the question
        categorizations = self.categorize_with_openai(question)

        try:
            json_categorizations = json.loads(categorizations)
            related_categories = "|".join(json_categorizations.get("related_categories", []))
            related_technologies = "|".join(json_categorizations.get("related_technologies", []))
            related_skills = "|".join(json_categorizations.get("related_skills", []))

            question['related_categories'] = related_categories
            question['related_technologies'] = related_technologies
            question['related_skills'] = related_skills
        except json.JSONDecodeError:
            print(f"Error parsing JSON for question: {question}")

        return question
    
    def categorize_all_questions(self):
        # Apply the categorization to all the question of the dataset
        self.questions = self.questions.progress_apply(self.save_question_categorization, axis=1)
    
    def export_categorizations(self):
        # save the categorization to a csv file,
        self.questions.to_csv(self.output_filename)

if __name__ == "__main__":

    arguments = parser.parse_args()

    # Columns of the CSV file: "Question #","Statement","My Answer","Expected Answer","Answer Status","Comments","Categories","GCP Services or Tools","Concepts or Topics"                                                                            
    questions = pd.read_csv(arguments.input, index_col=0, header=0)
    questions = questions.fillna("#EMPTY#")
    questions = questions.replace(["?","??","NaN"],"#EMPTY#")

    # Add categorization columns
    questions['related_categories'] = ''
    questions['related_technologies'] = ''
    questions['related_skills'] = ''

    # Use the QuestionCategorizer to categorize the dataframe questions
    categorizer = QuestionCategorizer(questions=questions, output_filename=arguments.output)
    categorizer.categorize_all_questions()
    categorizer.export_categorizations()



