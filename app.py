from flask import Flask, jsonify, request as flask_request
from flask_pymongo import PyMongo
from bson import ObjectId
import jwt
from flask_cors import CORS
import json
import pandas as pd

app = Flask(__name__)
CORS(app)
app.config['MONGO_URI'] = 'mongodb://127.0.0.1:27017/Learnlance'
mongo = PyMongo(app)

JWT_SECRET = '@insha@is@a@good@girl@'

def extract_user_id_from_token(token):
    try:
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        user_id = decoded_token.get('user', {}).get('id')
        return user_id
    except jwt.InvalidTokenError:
        return None

def calculate_rating(course):
    if course.get('rating'):
        feedback_array = list(map(int, course['rating'].split()))
        feedback = sum(feedback_array) / len(feedback_array) if feedback_array else 0
        return feedback
    return 5

@app.route('/')
def hello():
    return 'Hello, Flask!'

#JOBS RECOMMENDATION

@app.route('/api/GetRecommendedTeacherTopicRequest', methods=['GET'])
def get_teacher_topic_request():
    try:
        token = flask_request.headers.get('auth-token')
        teacher_profile_id = extract_user_id_from_token(token)

        teacher_profile = mongo.db.teacherprofiles.find_one({'teacher_profile_id': ObjectId(teacher_profile_id)})
        
        if not teacher_profile:
            return jsonify({'success': False, 'error': 'Teacher profile not found'}), 400

        else:

            bidded_topics = list(mongo.db.teacherbods.find({'teacher_id': ObjectId(teacher_profile_id)}))
            bidded_topics_id = [topic['topic_id'] for topic in bidded_topics]

            topicRequests = list(mongo.db.bidtopics.find({'_id': {'$nin': bidded_topics_id}}))

            user_topics = {}
            for topic in topicRequests:
                user_topics[str(topic['_id'])] = topic['skills_required']

            skills_str = teacher_profile.get('skills', '[]')
            teacherSkills = json.loads(skills_str)
            user_skills = [skill.get('name', '') for skill in teacherSkills]
            
            listedSkills = list(mongo.db.skills.find())
            all_skills = [skill.get('name', '') for skill in listedSkills]

            topics_matrix_data = []
            for user, topic_list in user_topics.items():
                row = [1 if skill in topic_list else 0 for skill in all_skills]
                topics_matrix_data.append(row)

            topics_matrix = pd.DataFrame(topics_matrix_data, index=user_topics.keys(), columns=all_skills)

            skills_matrix_data = []
            skills_matrix_data = [1 if skill in user_skills else 0 for skill in all_skills]
            skills_matrix = pd.DataFrame([skills_matrix_data], columns=all_skills, index=[teacher_profile_id])

            similaritySumAverage = []
            for user_skill in user_skills:
                user_similarity = {}
                for topic in user_topics:
                    user_set = set(topics_matrix.columns[topics_matrix.loc[topic] == 1])
                    skill_set = set(skills_matrix.columns[skills_matrix.loc[teacher_profile_id] == 1])
                    intersection_size = len(user_set.intersection(skill_set))
                    union_size = len(user_set.union(skill_set))
                    similarity = intersection_size / union_size if union_size != 0 else 0
                    user_similarity[topic] = similarity

                similaritySumAverage.append(user_similarity)

            user_index = 0

            sorted_topics = sorted(similaritySumAverage[user_index].items(), key=lambda x: x[1], reverse=True)
            filtered_topics = [(topic_name, similarity_score) for topic_name, similarity_score in sorted_topics if similarity_score > 0]
            top_5_topics_names = [topic_name for topic_name, _ in filtered_topics[:5]]
            print(f"Top 5 topics for user Insha: {top_5_topics_names}")

            topicsFinal = list(mongo.db.bidtopics.find())
            filtered_topics = [topic for topic in topicsFinal if str(topic.get("_id")) in top_5_topics_names]

            topic_request_info = []

            for req in filtered_topics:
                student_profile = mongo.db.studentprofiles.find_one({'student_profile_id': ObjectId(req['student_id'])})
                user = mongo.db.users.find_one({'_id': ObjectId(req['student_id'])})

                date = req['initiated_date']
                formatted_date = date.strftime('%d %b %Y')

                feedback = 0

                if 'feedback' in student_profile and student_profile['feedback']:
                    feedback_array = list(map(int, student_profile['feedback'].split()))
                    if feedback_array:
                        feedback = sum(feedback_array) / len(feedback_array)

                topic_request_info.append({
                    'topic_request_id': str(req['_id']),
                    'id': teacher_profile_id,
                    'student_id': str(req['student_id']),
                    'location': user['country'],
                    'language': req['language'],
                    'bid_count': req['bid_count'],
                    'initiated_date': formatted_date,
                    'title': req['title'],
                    'description': req['description'],
                    'rate_per_hour': req['rate_per_hour'],
                    'rate': feedback
                })

            return jsonify({'success': True, 'topicRequestInfo': topic_request_info})

    except Exception as error:
        return jsonify({'error': str(error)}), 500
    

#COURSES RECOMMENDATION
    
@app.route('/api/GetRecommendedCourses', methods=['GET'])
def get_courses():
    try:
        token = flask_request.headers.get('auth-token')
        student_profile_id = extract_user_id_from_token(token)
        student_profile = mongo.db.studentprofiles.find_one({'student_profile_id': ObjectId(student_profile_id)})

        if not student_profile:
            return jsonify({'success': False, 'error': 'Student profile not found'}), 400

        enrolled_courses = list(mongo.db.useritems.find({'student_id': ObjectId(student_profile_id), 'item_type': 'course'}))
        enrolled_course_ids = [course['item_id'] for course in enrolled_courses]

        courses = list(mongo.db.courses.find({'post_id': {'$nin': enrolled_course_ids}}))
        learning_posts = list(mongo.db.learningposts.find({'_id': {'$in': [course['post_id'] for course in courses]}}))

        user_courses = {}
        for course in courses:
            user_courses[str(course['post_id'])] = course['categories']

        interests_str = student_profile.get('interests', '[]')
        interests = json.loads(interests_str)
        user_interests = [interest.get('title', '') for interest in interests]
        
        interests = list(mongo.db.interests.find())
        all_interests = [interest.get('name', '') for interest in interests]

        courses_matrix_data = []
        for user, courses_list in user_courses.items():
            row = [1 if interest in courses_list else 0 for interest in all_interests]
            courses_matrix_data.append(row)

        courses_matrix = pd.DataFrame(courses_matrix_data, index=user_courses.keys(), columns=all_interests)

        interests_matrix_data = []
        interests_matrix_data = [1 if interest in user_interests else 0 for interest in all_interests]
        interests_matrix = pd.DataFrame([interests_matrix_data], columns=all_interests, index=[student_profile_id])

        similaritySumAverage = []
        for user_interest in user_interests:
            user_similarity = {}
            for course in user_courses:
                user_set = set(courses_matrix.columns[courses_matrix.loc[course] == 1])
                interest_set = set(interests_matrix.columns[interests_matrix.loc[student_profile_id] == 1])
                intersection_size = len(user_set.intersection(interest_set))
                union_size = len(user_set.union(interest_set))
                similarity = intersection_size / union_size if union_size != 0 else 0
                user_similarity[course] = similarity

            similaritySumAverage.append(user_similarity)

        user_index = 0

        sorted_courses = sorted(similaritySumAverage[user_index].items(), key=lambda x: x[1], reverse=True)
        filtered_courses = [(course_name, similarity_score) for course_name, similarity_score in sorted_courses if similarity_score > 0]
        top_5_course_names = [course_name for course_name, _ in filtered_courses[:5]]
        print(f"Top 5 courses for user Insha: {top_5_course_names}")

        coursesFinal = list(mongo.db.courses.find())
        filtered_courses = [course for course in coursesFinal if str(course.get("post_id")) in top_5_course_names]
        learning_postsFinal = list(mongo.db.learningposts.find({'_id': {'$in': [course['post_id'] for course in filtered_courses]}}))

        courses_with_learning_posts = [
            {
                '_id': str(course['_id']),
                'learning_post': str(course['post_id']),
                'fees': course['fees'],
                'title': next((post['title'] for post in learning_postsFinal if post['_id'] == course['post_id']), ''),
                'featured_image': next((post['featured_image'] for post in learning_postsFinal if post['_id'] == course['post_id']), ''),
                'rating': calculate_rating(course),
            }
            for course in filtered_courses if 'post_id' in course
        ]

        success = True
        return jsonify({'success': success, 'coursesWithLearningPosts': courses_with_learning_posts})

    except Exception as error:
        return jsonify({'error': str(error)}), 500
    
if __name__ == '__main__':
    app.run(host='192.168.0.147', debug=True)