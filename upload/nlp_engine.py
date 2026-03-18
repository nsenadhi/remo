import os
import pandas as pd
import json
from datetime import datetime
from config_nlp_engine import SYSTEM_PROMPT_INTENT_DETECTION, \
    SYSTEM_PROMPT_VISION, \
    SYSTEM_PROMPT_ENDPOINT, \
    TEXT_ENDPOINT_FORMAT, \
    INPUT_VISION

from utils import *
from request_to_openai import gpt
import logging

logger = logging.getLogger(__name__)

system_prompt_intent_detection = SYSTEM_PROMPT_INTENT_DETECTION
system_prompt_vision = SYSTEM_PROMPT_VISION
system_prompt_endpoint = SYSTEM_PROMPT_ENDPOINT
text_endpoint_format = TEXT_ENDPOINT_FORMAT

patient_meta_df = pd.read_csv('./static/local_data/fake_patient_meta_data.csv')


class nlp_engine():
    def __init__(self):
        self.patient_id = None
        self.image_description = 'None'
        self.vital_signs_text = 'None'
        self.show_data_list = []
        self.intent_dict = {}
        self.patient_meta_df = pd.read_csv('./static/local_data/fake_patient_meta_data.csv')
        self.last_response_id = None
        self.last_intent_context = None
        self._whitespace_re = re.compile(r'\n{2,}')  # ✅ NEW: Track last successful intent

    def intent_detection(self, doctor_question, previous_response_id=None):

        if not doctor_question:
            return False

        # ✅ Build context-aware prompt for follow-up questions
        enhanced_question = doctor_question
        
        if self.last_intent_context and previous_response_id:
            # Add context from last successful intent
            context_hint = f"\n\nPREVIOUS CONTEXT:\n"
            
            if self.last_intent_context.get('patient_id'):
                context_hint += f"Patient ID: {self.last_intent_context['patient_id']}\n"
            
            if self.last_intent_context.get('list_date'):
                dates = self.last_intent_context['list_date']
                if len(dates) > 1:
                    context_hint += f"Time Period: {dates[0]} to {dates[-1]}\n"
                elif len(dates) == 1:
                    context_hint += f"Date: {dates[0]}\n"
            
            context_hint += "\nIf the user's question refers to 'this period', 'that time', 'above period', etc., use the dates from the previous context.\n"
            
            enhanced_question = context_hint + "\nUSER QUESTION: " + doctor_question
            
            logger.info(f"📎 Adding context to intent detection from previous query")

        # ✅ CRITICAL: DO NOT pass previous_response_id to intent detection
        # Intent detection should be stateless - only the endpoint uses chaining
        intent, _ = gpt(
            system_prompt=SYSTEM_PROMPT_INTENT_DETECTION.format(
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            text=enhanced_question,
            model_name="gpt-4",
            temperature=0.1,
            previous_response_id=None,  # ✅ CHANGED: Always None for intent
            use_responses_api=False  # ✅ CHANGED: Use standard API for intent
        )
        
        try:
            intent_dict = json.loads(intent)
            self.intent_dict = intent_dict
            
            # ✅ Store successful intent for next query's context
            if intent_dict.get('patient_id') or intent_dict.get('list_date'):
                self.last_intent_context = {
                    'patient_id': intent_dict.get('patient_id'),
                    'list_date': intent_dict.get('list_date', []),
                    'vital_sign': intent_dict.get('vital_sign', [])
                }
                logger.debug(f"📎 Stored intent context for next query")
            
            logger.info('=========INTENT==========')
            logger.info(intent_dict)
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Intent detection returned invalid JSON: {e}")
            logger.error(f"   Response was: {intent[:200]}...")
            
            # ✅ Fallback: Try to extract info from natural language response
            # This handles cases where AI responds conversationally
            logger.warning("⚠️ Attempting to salvage intent from natural language response...")
            
            # Use last context if available
            if self.last_intent_context:
                self.intent_dict = {
                    'patient_id': self.last_intent_context.get('patient_id', ''),
                    'list_date': self.last_intent_context.get('list_date', []),
                    'list_time': [],
                    'vital_sign': self._extract_vitals_from_text(doctor_question),
                    'is_plot': 'plot' in doctor_question.lower() or 'graph' in doctor_question.lower(),
                    'recognition': False,
                    'is_image': False,
                    'data_format': 'analysis' if 'analyze' in doctor_question.lower() else 'raw'
                }
                logger.info(f"✅ Salvaged intent using context: {self.intent_dict}")
                return True
            
            # Final fallback
            self.intent_dict = {
                "patient_id": "",
                "list_date": [],
                "list_time": [],
                "vital_sign": [],
                "is_plot": False,
                "recognition": False,
                "is_image": False,
                "data_format": "raw"
            }
            return False

    def _extract_vitals_from_text(self, text):
        """✅ Helper: Extract vital signs from natural language"""
        text_lower = text.lower()
        vitals = []
        
        vital_keywords = {
            'heart_rate': ['heart rate', 'pulse', 'hr', 'heartbeat'],
            'blood_pressure': ['blood pressure', 'bp', 'systolic', 'diastolic'],
            'oxygen_saturation': ['oxygen', 'spo2', 'saturation', 'o2'],
            'body_temperature': ['temperature', 'temp', 'fever'],
            'respiratory_rate': ['respiratory', 'breathing', 'respiration'],
            'glucose': ['glucose', 'blood sugar', 'sugar level']
        }
        
        for vital, keywords in vital_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                vitals.append(vital)
        
        return vitals

    def vision_llm(self, image_path_list: list):
        logger.info('==== IMAGE PATH LIST ====')
        logger.info(image_path_list)

        if not image_path_list:
            self.image_description = 'Can not get image data'
            return self.image_description
        for image_path in image_path_list:
            if not os.path.exists(image_path):
                return 'Can not find image'

        image_description, _ = gpt(
            text=INPUT_VISION,
            model_name="gpt-4-vision-preview",
            image_path=image_path_list,
            system_prompt=SYSTEM_PROMPT_VISION,
            temperature=0.4,
            use_responses_api=False
        )
        self.image_description = image_description
        return self.image_description

    def endpoint_llm(self, patient_info, doctor_question, previous_response_id=None, conversation_history=None):
        """✅ UNCHANGED: Endpoint DOES use conversation chaining"""
        text_endpoint = TEXT_ENDPOINT_FORMAT.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            patient_id=self.patient_id,
            name=patient_info['name'].values[0],
            sex=patient_info['sex'].values[0],
            address=patient_info['address'].values[0],
            phone=patient_info['phone'].values[0],
            dob=patient_info['birth'].values[0],
            age=patient_info['age'].values[0],
            image_description=self.image_description,
            vital_signs_data=self.vital_signs_text,
            question=doctor_question
        )

        logger.info('=========TEXT ENDPOINT==========')
        logger.info(text_endpoint)

        def _sanitize_response(text: str) -> str:
            if not isinstance(text, str):
                return text
            cleaned = self._whitespace_re.sub('\n', text).strip()
            cleaned = re.sub(r'\n(\s*[\u2022\-\*])', r'\n\1', cleaned)
            return cleaned

        try:
            output, response_id = gpt(
                system_prompt=SYSTEM_PROMPT_ENDPOINT,
                text=text_endpoint,
                model_name="gpt-4",
                temperature=0.2,
                previous_response_id=previous_response_id,  # ✅ Endpoint DOES chain
                use_responses_api=True
            )
            self.last_response_id = response_id
            return _sanitize_response(output), response_id
        except ValueError as e:
            logger.error(f"Error unpacking response from gpt(): {e}")
            output = gpt(
                system_prompt=SYSTEM_PROMPT_ENDPOINT,
                text=text_endpoint,
                model_name="gpt-4",
                temperature=0.2,
                use_responses_api=False
            )
            return _sanitize_response(output), None

    def _is_valid_id(self):
        if bool(re.match(r'^\d{5}$', self.intent_dict['patient_id'])):
            if int(self.intent_dict['patient_id']) in self.patient_meta_df['patient_id'].values:
                return True
            else:
                return False
        else:
            return False

    def _ask_for_id(self):
        while True:
            temp = input('I did not receive a valid patient ID number. Please provide a valid ID number.')

            if temp == '':
                return False

            temp_patient_id = extract_patient_id_from_text(temp)

            if is_valid_id(temp_patient_id, self.patient_meta_df):
                break

        return temp_patient_id

    def check_and_update_patient_id(self):
        if self._is_valid_id():
            self.patient_id = self.intent_dict['patient_id']
        else:
            if not self.patient_id:
                new_id = self._ask_for_id()
                if not new_id:
                    return False
                else:
                    self.patient_id = new_id
                    self.intent_dict['patient_id'] = new_id
        return True

    def process_special_historical_data_retrieval(self):
        if (len(self.intent_dict['list_date']) == 0) and (len(self.intent_dict['list_time']) == 0):
            return
        if len(self.intent_dict['list_date']) == 0:
            self.intent_dict['list_date'] = [datetime.now().strftime("%Y-%m-%d")]

        if len(self.intent_dict['list_time']) == 0:
            self.intent_dict['list_time'] = ['01:00:00', '07:00:00', '13:00:00', '19:00:00']




'''
def NLP_engine(doctor_question):
    # initialize variables
    image_description = 'None'
    vital_signs_text = 'None' 
    show_list = [] # save image_path or plot_path that would be used to shown to the user

    ################################
    ##########   INTENT   ##########
    ################################

    intent = gpt(system_prompt=system_prompt_intent_detection, text=doctor_question, model_name="gpt-3.5-turbo", temperature=0.1)
    intent_dict = json.loads(intent)
    #print(intent_dict) #debug
    #print()



    # check the valid patient_id (did the user provide this information yet? does the id appear in the database?):
    patient_id =  get_id(intent_dict['patient_id'], patient_meta_df)

    if not patient_id: # if the user cannot provide a valid patient_id, the session will stop
        return "Exit", show_list
    else: 
        intent_dict['patient_id'] = patient_id # update the new valid patient_id into the intent_dict


    ################################
    ########## VITAL SIGN ##########
    ################################

    if len(intent_dict['vital_sign'])>0: # check if we need to get the vital sign
        ########## get real-time data from the EDGE DEVICE ##########
        if (len(intent_dict['list_date']) == 0) and (len(intent_dict['list_time']) == 0): 
            ############################# TODO: get data from EDGE DEVICE with values in keys of 'patient_id', 'vital_sign'
            vital_sign_df = pd.read_csv('tmp/2024_03.csv') 
            #############################

            vital_signs_text = df_to_text(vital_sign_df, intent_dict, is_current=True)

        ########## get real-time data from the AWS S3 ##########
        else: 
            # process some special case
            if len(intent_dict['list_date']) == 0: # the patient ask for data in some sessions in the current day, ex. today morning, this evening
                intent_dict['list_date'] = [datetime.now().strftime("%Y-%m-%d")]
                #print('a')
            if len(intent_dict['list_time']) == 0:  # the patient ask for data in some day without providing the time, ex. last 3 days, last week
                intent_dict['list_time'] = ['08:00:00']
                #print('b')
            ############################# TODO: get data from S3 with values in keys of 'patient_id', 'list_date', 'list_time', 'vital_sign'
            vital_sign_df = pd.read_csv('tmp/2024_03.csv') 
            #############################
            vital_signs_text = df_to_text(vital_sign_df, intent_dict, is_current=False)


            ########## PLOT ##########

            if intent_dict['is_plot']:
                # TODO: draw plot function ############################
                # use df directly to plot
                # save plot image and add the path to show_plot_list
                print('Plotted')
    print(intent_dict) #DEBUG    

    ################################
    ##########   IMAGES   ##########
    ################################

    if intent_dict['recognition'] or intent_dict['is_image']: # check if we need to get the vital sign
        ########## get real-time image from the EDGE DEVICE ##########
        if len(intent_dict['list_date']) == 0 and len(intent_dict['list_time']) == 0: 
            ############################# TODO: get image from S3
            image_path = ['tmp/HACER_mid_frame/putonglasses_angry_7_j.png']
            #############################

        ########## get real-time data from the AWS S3 ##########
        else: 
            ############################# TODO: get image from AWS S3
            image_path = ['tmp/HACER_mid_frame/putonglasses_angry_7_j.png']
            #############################

        ########## RECOGNITION ##########
        if intent_dict['recognition']:
            text_vision = "Classify the activities and emotions in this image."
            image_description = gpt(
                text = text_vision,
                model_name="gpt-4-vision-preview", 
                image_path = ['tmp/HACER_mid_frame/putonglasses_angry_7_j.png'], ############################# TODO: change image path  ############################
                system_prompt = system_prompt_vision,
                temperature = 0.2
            ) 


        if intent_dict['is_image']:
            ############################# TODO: add image path to show_image_list
            print('Showed image')

    ################################
    #########   ENDPOINT   #########
    ################################

    patient_info = patient_meta_df[patient_meta_df['patient_id']==int(patient_id)]

    text_endpoint = text_endpoint_format.format(current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                patient_id = patient_id,
                                name = patient_info['name'].values[0], 
                                sex = patient_info['sex'].values[0], 
                                address = patient_info['address'].values[0], 
                                phone = patient_info['phone'].values[0], 
                                dob = patient_info['birth'].values[0], 
                                age = patient_info['age'].values[0], 
                                image_description = image_description, 
                                vital_signs_data = vital_signs_text, 
                                question = doctor_question)
    print(text_endpoint) #DEBUG
    print()

    output = 'Done'
    #output = gpt(system_prompt=system_prompt_endpoint, text=text_endpoint, model_name="gpt-3.5-turbo", temperature=0.1)

    return output, show_list

doctor_question = 'What is the current heart rate of the patient? 00001'
#doctor_question = q51
response, show_list = NLP_engine(doctor_question)
print('==============')
print()
print(response) '''