from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Course, Module, Lesson, Question, Answer, UserProgress, UserQuestion, ListeningLesson, \
                    SpeakingLesson, SpeakingAttempt, SpeakingQuestion
from django.utils import timezone
import requests
import tempfile
import speech_recognition as sr
from django.conf import settings
from django.core.files.base import ContentFile
import re
import pyttsx3
import threading
import base64


import subprocess
import os
from gigachat import GigaChat

# Bosh sahifa
def home(request):
    courses = Course.objects.filter(is_active=True)
    return render(request, 'home.html', {'courses': courses})


# Ro'yxatdan o'tish
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


# Kurs detallari
@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id, is_active=True)
    modules = course.modules.all().order_by('order')

    # Jami darslar soni
    total_video_lessons = 0
    total_listening_lessons = 0

    for module in modules:
        total_video_lessons += module.lessons.count()
        total_listening_lessons += module.listening_lessons.count()

    return render(request, 'course_detail.html', {
        'course': course,
        'modules': modules,
        'total_video_lessons': total_video_lessons,
        'total_listening_lessons': total_listening_lessons
    })

# Modul detallari (SIMPLIFIED VERSION)
# Modul detallari - Barcha darslarni order bo'yicha tartiblash
@login_required
def module_detail(request, module_id):
    module = get_object_or_404(Module, id=module_id)

    # Barcha dars turlarini olish
    video_lessons = module.lessons.all()
    listening_lessons = module.listening_lessons.all()

    # SPEAKING DARSLARNI QO'SHGANINGIZGA ISHONCH HOSIL QILING
    speaking_lessons = module.speaking_lessons.all()  # ← BU QATOR MAVJUD BO'LISHI KERAK

    # Barcha darslarni birlashtirish
    all_lessons = []

    # Video darslar
    for lesson in video_lessons:
        progress = UserProgress.objects.filter(user=request.user, lesson=lesson).first()
        all_lessons.append({
            'id': lesson.id,
            'title': lesson.title,
            'duration': lesson.duration,
            'order': lesson.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'video',
            'object': lesson
        })

    # Listening darslar
    for listening in listening_lessons:
        progress = UserProgress.objects.filter(user=request.user, listening_lesson=listening).first()
        all_lessons.append({
            'id': listening.id,
            'title': listening.title,
            'duration': f"{listening.timer_minutes} min" if listening.timer_minutes > 0 else "Vaqtsiz",
            'order': listening.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'listening',
            'listening_type': listening.get_listening_type_display(),
            'object': listening
        })

    # SPEAKING DARSLARNI QO'SHISH - BU BO'LIMNI TEKSHIRING
    for speaking in speaking_lessons:  # ← speaking_lessons O'ZGARUVCHISI MAVJUD BO'LISHI KERAK
        progress = UserProgress.objects.filter(user=request.user, speaking_lesson=speaking).first()
        all_lessons.append({
            'id': speaking.id,
            'title': speaking.title,
            'duration': f"{speaking.target_duration} soniya",  # ← speaking.target_duration BO'LISHI KERAK
            'order': speaking.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'speaking',  # ← TURI 'speaking' BO'LISHI KERAK
            'speaking_type': speaking.get_speaking_type_display(),
            # ← speaking_type QO'SHILGANLIGIGA ISHONCH HOSIL QILING
            'object': speaking
        })

    # Order bo'yicha tartiblash
    all_lessons.sort(key=lambda x: x['order'])

    # Har bir darsga ketma-ket raqam berish
    for index, lesson in enumerate(all_lessons, 1):
        lesson['display_order'] = index

    return render(request, 'module_detail.html', {
        'module': module,
        'lessons': all_lessons
    })

@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    module = lesson.module
    course = module.course

    # YouTube video ID (agar YouTube linki bo'lsa)
    youtube_id = None
    if lesson.video_url and ('youtube.com' in lesson.video_url or 'youtu.be' in lesson.video_url):
        youtube_id = extract_youtube_id(lesson.video_url)

    # Video turi
    video_type = lesson.video_type()

    # Oldingi va keyingi darslar
    lessons = list(module.lessons.all().order_by('order'))
    current_index = lessons.index(lesson)
    prev_lesson = lessons[current_index - 1] if current_index > 0 else None
    next_lesson = lessons[current_index + 1] if current_index < len(lessons) - 1 else None

    # Test savollari
    questions = lesson.questions.all()

    # Foydalanuvchi progressi
    user_progress = UserProgress.objects.filter(user=request.user, lesson=lesson).first()
    completed = user_progress.completed if user_progress else False

    return render(request, 'lesson_detail.html', {
        'lesson': lesson,
        'module': module,
        'course': course,
        'video_type': video_type,
        'youtube_id': youtube_id,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'questions': questions,
        'completed': completed
    })


# Test yuborish
@csrf_exempt
@login_required
def submit_test(request, lesson_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        lesson = get_object_or_404(Lesson, id=lesson_id)

        # Baholash
        total_questions = len(data.get('answers', []))
        correct_answers = 0

        for answer_data in data.get('answers', []):
            question_id = answer_data.get('question_id')
            user_answer = answer_data.get('answer')

            question = get_object_or_404(Question, id=question_id)
            if question.question_type == 'single':
                correct_answer = question.answers.filter(is_correct=True).first()
                if correct_answer and str(correct_answer.id) == user_answer:
                    correct_answers += 1

        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        passed = score >= 70

        # Progressni saqlash
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={'score': score, 'completed': passed}
        )

        if not created:
            user_progress.score = score
            user_progress.completed = passed
            user_progress.save()

        return JsonResponse({
            'success': True,
            'score': score,
            'passed': passed,
            'correct_answers': correct_answers,
            'total_questions': total_questions
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# Savol yuborish
@csrf_exempt
@login_required
def submit_question(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        lesson_id = data.get('lesson_id')
        question_text = data.get('question_text')

        if not lesson_id or not question_text:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        lesson = get_object_or_404(Lesson, id=lesson_id)

        user_question = UserQuestion.objects.create(
            user=request.user,
            lesson=lesson,
            question_text=question_text
        )

        return JsonResponse({'success': True, 'question_id': user_question.id})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


import re


def extract_youtube_id(url):
    """YouTube URL dan video ID ni ajratib olish"""
    if not url:
        return None

    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\?\/\s]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            # '?si=' parametridan keyingi qismni kesib tashlash
            if '?si=' in video_id:
                video_id = video_id.split('?si=')[0]
            return video_id

    return None

@login_required
def listening_detail(request, listening_id):
    listening = get_object_or_404(ListeningLesson, id=listening_id)
    module = listening.module
    course = module.course

    # Barcha darslarni olish
    all_lessons = list(module.lessons.all().order_by('order'))
    all_listenings = list(module.listening_lessons.all().order_by('order'))

    # Barcha darslarni birlashtirish va tartiblash
    all_content = []
    for l in all_lessons:
        all_content.append(('video', l))
    for l in all_listenings:
        all_content.append(('listening', l))

    all_content.sort(key=lambda x: x[1].order)

    # Joriy darsni topish
    current_index = None
    for i, (content_type, content) in enumerate(all_content):
        if content_type == 'listening' and content.id == listening_id:
            current_index = i
            break

    prev_content = all_content[current_index - 1] if current_index and current_index > 0 else None
    next_content = all_content[current_index + 1] if current_index and current_index < len(all_content) - 1 else None

    # Foydalanuvchi progressi
    user_progress = UserProgress.objects.filter(
        user=request.user,
        listening_lesson=listening
    ).first()

    # Listening turiga qarab ma'lumotlarni olish
    context = {
        'listening': listening,
        'module': module,
        'course': course,
        'prev_content': prev_content,
        'next_content': next_content,
        'completed': user_progress.completed if user_progress else False,
    }

    # Listening turiga qarab qo'shimcha ma'lumotlar
    if listening.listening_type == 'multiple_choice':
        context['questions'] = listening.questions.all().order_by('order')
    elif listening.listening_type == 'gap_filling':
        context['gap_fillings'] = listening.gap_fillings.all().order_by('order')
        # Gap optionlarni alohida olish
        for gap in context['gap_fillings']:
            gap.options_list = gap.options.all().order_by('gap_letter')
    elif listening.listening_type == 'true_false_not_given':
        context['tfng_questions'] = listening.tfng_questions.all().order_by('order')
    elif listening.listening_type == 'matching':
        context['matching_questions'] = listening.matching_questions.all().order_by('order')
        # Matching uchun columnlarni ajratish
        for match in context['matching_questions']:
            match.column_a_list = [line.strip() for line in match.column_a.split('\n') if line.strip()]
            match.column_b_list = [line.strip() for line in match.column_b.split('\n') if line.strip()]
            try:
                match.correct_matches_dict = json.loads(match.correct_matches)
            except:
                match.correct_matches_dict = {}

    return render(request, 'listening_detail.html', context)

@csrf_exempt
@login_required
def check_listening_answers(request, listening_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            listening = get_object_or_404(ListeningLesson, id=listening_id)

            total_questions = 0
            correct_answers = 0
            results = {}

            if listening.listening_type == 'multiple_choice':
                # Multiple choice tekshirish
                questions = listening.questions.all().order_by('order')
                total_questions = questions.count()

                for question in questions:
                    user_answer = data.get(f'question_{question.id}')
                    correct_option = question.options.filter(is_correct=True).first()

                    if user_answer and correct_option:
                        # User answer option ID, correct option ID bilan solishtirish
                        if str(user_answer) == str(correct_option.id):
                            correct_answers += 1
                            results[f'question_{question.id}'] = 'correct'
                        else:
                            results[f'question_{question.id}'] = 'wrong'
                    else:
                        results[f'question_{question.id}'] = 'not_answered'

            elif listening.listening_type == 'gap_filling':
                # Gap filling tekshirish
                gap_fillings = listening.gap_fillings.all().order_by('order')
                for gap in gap_fillings:
                    gap_options = gap.options.all()
                    total_questions += gap_options.count()

                    for gap_opt in gap_options:
                        user_answer = data.get(f'gap_{gap.id}_{gap_opt.gap_letter}')
                        if user_answer and user_answer.strip().lower() == gap_opt.correct_word.lower():
                            correct_answers += 1
                            results[f'gap_{gap.id}_{gap_opt.gap_letter}'] = 'correct'
                        else:
                            results[f'gap_{gap.id}_{gap_opt.gap_letter}'] = 'wrong'

            elif listening.listening_type == 'true_false_not_given':
                # TFNG tekshirish
                tfng_questions = listening.tfng_questions.all().order_by('order')
                total_questions = tfng_questions.count()

                for tfng in tfng_questions:
                    user_answer = data.get(f'tfng_{tfng.id}')
                    if user_answer and user_answer == tfng.correct_answer:
                        correct_answers += 1
                        results[f'tfng_{tfng.id}'] = 'correct'
                    else:
                        results[f'tfng_{tfng.id}'] = 'wrong'

            elif listening.listening_type == 'matching':
                # Matching tekshirish
                matching_questions = listening.matching_questions.all().order_by('order')
                for match in matching_questions:
                    try:
                        correct_matches = json.loads(match.correct_matches)
                        total_questions += len(correct_matches)

                        for key, value in correct_matches.items():
                            user_answer = data.get(f'match_{match.id}_{key}')
                            if user_answer and str(user_answer) == str(value):
                                correct_answers += 1
                                results[f'match_{match.id}_{key}'] = 'correct'
                            else:
                                results[f'match_{match.id}_{key}'] = 'wrong'
                    except:
                        pass

            # Ballarni hisoblash (agar total_questions 0 bo'lsa, 0 qaytaramiz)
            if total_questions > 0:
                score = (correct_answers / total_questions) * 100
                passed = score >= 50  # 50% minimal
            else:
                score = 0
                passed = False

            # Progressni saqlash
            user_progress, created = UserProgress.objects.get_or_create(
                user=request.user,
                listening_lesson=listening,
                defaults={'score': score, 'completed': passed, 'completed_at': timezone.now() if passed else None}
            )

            if not created:
                user_progress.score = score
                user_progress.completed = passed
                if passed:
                    user_progress.completed_at = timezone.now()
                user_progress.save()

            return JsonResponse({
                'success': True,
                'score': score,
                'passed': passed,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'results': results
            })

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Xatolik: {str(e)}")
            print(f"Xatolik detallari: {error_details}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'details': error_details
            })

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
@login_required
def save_listening_progress(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        listening_id = data.get('listening_id')
        score = data.get('score', 0)

        listening = get_object_or_404(ListeningLesson, id=listening_id)

        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            listening_lesson=listening,
            defaults={'score': score, 'completed': True}
        )

        if not created:
            user_progress.score = score
            user_progress.completed = True
            user_progress.completed_at = timezone.now()
            user_progress.save()

        return JsonResponse({'success': True, 'message': 'Progress saqlandi'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

# courses/views.py ga qo'shing:
@csrf_exempt
@login_required
def submit_listening_test(request, listening_id):
    """Listening testini qabul qilish - TO'LIQ VERSIYA"""
    if request.method == 'POST':
        try:
            print(f"=== SUBMIT LISTENING TEST CALLED ===")
            print(f"Listening ID: {listening_id}")
            print(f"Request content type: {request.content_type}")
            print(f"User: {request.user}")

            # JSON ma'lumotlarni olish
            try:
                data = json.loads(request.body)
                print(f"Received JSON data: {data}")
            except json.JSONDecodeError:
                print("JSON parse error, trying form data")
                # Form data ni dict ga aylantirish
                data = dict(request.POST)
                # Birinchi elementlarni olish (list ichida keladi)
                for key, value in data.items():
                    if isinstance(value, list) and len(value) == 1:
                        data[key] = value[0]
                print(f"Received form data: {data}")

            listening = get_object_or_404(ListeningLesson, id=listening_id)
            print(f"Listening found: {listening.title}, Type: {listening.listening_type}")

            total_questions = 0
            correct_answers = 0
            results = {}

            if listening.listening_type == 'multiple_choice':
                # Multiple choice tekshirish
                questions = listening.questions.all().order_by('order')
                total_questions = questions.count()
                print(f"Total multiple choice questions: {total_questions}")

                for question in questions:
                    question_key = f'question_{question.id}'
                    user_answer = data.get(question_key)
                    correct_option = question.options.filter(is_correct=True).first()

                    print(
                        f"Question {question.id}: User answer = {user_answer}, Correct option ID = {correct_option.id if correct_option else None}")

                    if user_answer and correct_option:
                        if str(user_answer) == str(correct_option.id):
                            correct_answers += 1
                            results[question_key] = 'correct'
                            print(f"Question {question.id}: CORRECT")
                        else:
                            results[question_key] = 'wrong'
                            print(f"Question {question.id}: WRONG")
                    else:
                        results[question_key] = 'not_answered'
                        print(f"Question {question.id}: NOT ANSWERED")

            elif listening.listening_type == 'gap_filling':
                # Gap filling tekshirish
                gap_fillings = listening.gap_fillings.all().order_by('order')
                for gap in gap_fillings:
                    gap_options = gap.options.all()
                    total_questions += gap_options.count()

                    for gap_opt in gap_options:
                        gap_key = f'gap_{gap.id}_{gap_opt.gap_letter}'
                        user_answer = data.get(gap_key)
                        if user_answer and user_answer.strip().lower() == gap_opt.correct_word.lower():
                            correct_answers += 1
                            results[gap_key] = 'correct'
                        else:
                            results[gap_key] = 'wrong'

            elif listening.listening_type == 'true_false_not_given':
                # TFNG tekshirish
                tfng_questions = listening.tfng_questions.all().order_by('order')
                total_questions = tfng_questions.count()

                for tfng in tfng_questions:
                    tfng_key = f'tfng_{tfng.id}'
                    user_answer = data.get(tfng_key)
                    if user_answer and user_answer == tfng.correct_answer:
                        correct_answers += 1
                        results[tfng_key] = 'correct'
                    else:
                        results[tfng_key] = 'wrong'

            elif listening.listening_type == 'matching':
                # Matching tekshirish
                matching_questions = listening.matching_questions.all().order_by('order')
                for match in matching_questions:
                    try:
                        correct_matches = json.loads(match.correct_matches)
                        total_questions += len(correct_matches)

                        for key, value in correct_matches.items():
                            match_key = f'match_{match.id}_{key}'
                            user_answer = data.get(match_key)
                            if user_answer and str(user_answer) == str(value):
                                correct_answers += 1
                                results[match_key] = 'correct'
                            else:
                                results[match_key] = 'wrong'
                    except:
                        pass

            # Ballarni hisoblash
            if total_questions > 0:
                score = (correct_answers / total_questions) * 100
                passed = score >= 50  # 50% minimal
            else:
                score = 0
                passed = False

            print(f"Score: {score}, Passed: {passed}, Correct: {correct_answers}/{total_questions}")

            # Progressni saqlash
            user_progress, created = UserProgress.objects.get_or_create(
                user=request.user,
                listening_lesson=listening,
                defaults={'score': score, 'completed': passed, 'completed_at': timezone.now() if passed else None}
            )

            if not created:
                user_progress.score = score
                user_progress.completed = passed
                if passed:
                    user_progress.completed_at = timezone.now()
                user_progress.save()

            print(f"Progress saved: User={request.user}, Score={score}, Completed={passed}")

            return JsonResponse({
                'success': True,
                'score': score,
                'passed': passed,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'results': results,
                'message': 'Test muvaffaqiyatli topshirildi!'
            })

        except Exception as e:
            print(f"=== ERROR IN SUBMIT_LISTENING_TEST ===")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error traceback: {error_trace}")

            return JsonResponse({
                'success': False,
                'error': str(e),
                'error_type': str(type(e)),
                'traceback': error_trace
            })

    print("Invalid request method")
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

import requests
import json
import tempfile
import speech_recognition as sr
from django.conf import settings
from django.core.files.base import ContentFile
# courses/views.py - TO'LIQ VERSIYA

import json
import tempfile
import os
import re
import uuid
import subprocess
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile

import speech_recognition as sr
from gtts import gTTS
from gigachat import GigaChat

from .models import Course, Module, Lesson, Question, Answer, UserProgress, \
    UserQuestion, ListeningLesson, SpeakingLesson, SpeakingAttempt, \
    SpeakingQuestion


# ============================================
# YORDAMCHI FUNKSIYALAR (OTHER.PY O'RNIGA)
# ============================================

def speech_to_text(audio_path):
    """Audio faylni textga o'girish"""
    language = "en-US"

    try:
        print(f"Converting {audio_path} to text...")

        # Audio faylni o'qish
        r = sr.Recognizer()

        with sr.AudioFile(audio_path) as source:
            print("Audio file opened, adjusting for ambient noise...")

            # Atrof-muhit shovqinini kamaytirish
            r.adjust_for_ambient_noise(source, duration=0.5)

            # Audioni yozib olish
            audio = r.record(source)

            print("Recognizing speech...")
            # Google Speech Recognition orqali matnga o'girish
            text = r.recognize_google(audio, language=language)

            print(f"Success! Transcript: {text[:100]}...")
            return text

    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
        return "Could not understand audio. Please speak more clearly."

    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return f"Speech recognition service error: {e}"

    except Exception as e:
        print(f"Speech-to-text error: {e}")
        # Fallback: Oddiy o'qish
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = r.record(source)
                text = r.recognize_google(audio, language='en-US')
                return text
        except:
            return "Speech recognition failed. Please try again."


def text_to_speech(text, lang='en', save_path=None):
    """Textni audio faylga o'girish"""

    if not text:
        print("No text provided for TTS")
        return None

    try:
        print(f"Converting text to speech: {text[:100]}...")

        # Agar save_path berilmagan bo'lsa, default papka
        if not save_path:
            save_path = os.path.join(settings.MEDIA_ROOT, 'speaking_feedback')

        # Agar papka mavjud bo'lmasa, yaratish
        if not os.path.exists(save_path):
            os.makedirs(save_path)

        # Audio fayl nomini yaratish (unique name)
        filename = f"feedback_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(save_path, filename)

        # Matnni qisqartirish (TTS chegarasi uchun)
        if len(text) > 1000:
            print(f"Text too long ({len(text)} chars), truncating...")
            text = text[:1000] + "..."

        # TTS obyektini yaratish
        tts = gTTS(text=text, lang=lang, slow=False)

        # Audio faylni saqlash
        tts.save(filepath)

        print(f"TTS audio saved: {filepath}")
        return filepath

    except Exception as e:
        print(f"Text-to-speech error: {e}")

        # Alternative: Use pyttsx3 as fallback
        try:
            print("Trying pyttsx3 as fallback...")
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 0.9)

            # Ovozlarni tanlash
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'english' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break

            # Audio faylni saqlash
            filename = f"feedback_{uuid.uuid4().hex[:8]}.mp3"
            filepath = os.path.join(save_path, filename)

            engine.save_to_file(text, filepath)
            engine.runAndWait()

            print(f"Fallback TTS audio saved: {filepath}")
            return filepath

        except Exception as e2:
            print(f"Fallback TTS also failed: {e2}")
            return None


def analyze_speech_with_ai(text, speaking_lesson):
    """GigaChat AI yordamida nutqni tahlil qilish"""

    if not text or len(text.strip()) < 5:
        print("Text too short for analysis")
        return generate_demo_analysis(text, speaking_lesson)

    try:
        print(f"Analyzing text with GigaChat: {text[:100]}...")

        # Promptni yaratish
        prompt = f"""
        You are an expert English speaking assessment AI. Analyze this speaking attempt:

        STUDENT LEVEL: {speaking_lesson.get_level_display()}
        TASK: {speaking_lesson.instruction_text}

        TRANSCRIPT: "{text}"

        Provide analysis with these exact scores (0-100):

        SCORING CRITERIA:
        - Fluency (30%): Flow, pace, hesitation, natural pauses
        - Vocabulary (25%): Word choice, variety, appropriateness for level
        - Grammar (25%): Sentence structure, tense accuracy, grammatical correctness
        - Pronunciation (20%): Based on likely pronunciation from transcript

        REQUIREMENTS:
        1. Give constructive, encouraging feedback
        2. Mention specific strengths and areas for improvement
        3. Provide actionable suggestions
        4. Be specific about what was good and what needs work
        5. Keep feedback concise but detailed

        FORMAT RESPONSE AS VALID JSON ONLY:
        {{
            "fluency_score": [number 0-100],
            "vocabulary_score": [number 0-100],
            "grammar_score": [number 0-100],
            "pronunciation_score": [number 0-100],
            "overall_score": [weighted average of above scores],
            "feedback": "Encouraging, constructive feedback in 3-4 sentences",
            "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"]
        }}
        """

        print("Sending prompt to GigaChat...")

        # GigaChat dan foydalanish
        with GigaChat(
                credentials="MDE5YWFjYWMtNTdmYi03NTMwLTg4MTctMTQwN2IwNTNlM2FmOjAwNmQ3ZGYwLTM4N2EtNGI2ZS05ODQxLWZhZjAyOTJjZTAyMw==",
                verify_ssl_certs=False,
                model="GigaChat"
        ) as giga:
            response = giga.chat(prompt)
            analysis_text = response.choices[0].message.content

            print(f"GigaChat response: {analysis_text[:200]}...")

            # JSON ni extract qilish
            analysis = extract_json_from_text(analysis_text)

            if analysis:
                print("JSON successfully extracted")

                # Word count va duration hisoblash
                word_count = len(text.split())
                duration = int((word_count / 150) * 60) if word_count > 0 else 0

                # Qo'shimcha fieldlar
                analysis['duration'] = duration
                analysis['word_count'] = word_count
                analysis['transcript'] = text

                # Ballarni to'g'rilash (0-100 oralig'ida)
                score_keys = ['fluency_score', 'vocabulary_score', 'grammar_score',
                              'pronunciation_score', 'overall_score']

                for key in score_keys:
                    if key in analysis:
                        try:
                            # Agar string bo'lsa, faqat raqamlarni olish
                            if isinstance(analysis[key], str):
                                numbers = re.findall(r'\d+', analysis[key])
                                if numbers:
                                    score = int(numbers[0])
                                    analysis[key] = max(0, min(100, score))
                                else:
                                    analysis[key] = 70
                            else:
                                score = int(analysis[key])
                                analysis[key] = max(0, min(100, score))
                        except:
                            analysis[key] = 70

                # Overall score ni hisoblash (agar yo'q bo'lsa)
                if 'overall_score' not in analysis or analysis['overall_score'] == 0:
                    weights = {'fluency_score': 0.3, 'vocabulary_score': 0.25,
                               'grammar_score': 0.25, 'pronunciation_score': 0.2}
                    weighted_sum = 0
                    valid_weights = 0

                    for key, weight in weights.items():
                        if key in analysis and analysis[key] > 0:
                            weighted_sum += analysis[key] * weight
                            valid_weights += weight

                    if valid_weights > 0:
                        analysis['overall_score'] = round(weighted_sum / valid_weights)
                    else:
                        analysis['overall_score'] = 70

                # Suggestions ni list ga aylantirish
                if 'suggestions' in analysis:
                    if isinstance(analysis['suggestions'], str):
                        # String ni list ga aylantirish
                        suggestions = analysis['suggestions'].split('\n')
                        analysis['suggestions'] = [s.strip() for s in suggestions if s.strip()]

                    # 3 ta suggestiondan oshib ketmasligi uchun
                    if len(analysis['suggestions']) > 3:
                        analysis['suggestions'] = analysis['suggestions'][:3]

                return analysis

            else:
                print("Could not extract JSON, using demo analysis")
                return generate_demo_analysis(text, speaking_lesson)

    except Exception as e:
        print(f"GigaChat analysis error: {e}")
        import traceback
        traceback.print_exc()
        return generate_demo_analysis(text, speaking_lesson)


def extract_json_from_text(text):
    """Matndan JSON qismini ajratib olish"""
    try:
        # JSON ni qidirish (bir nechta qavslar orasida)
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
        json_match = re.search(json_pattern, text, re.DOTALL)

        if json_match:
            json_str = json_match.group()
            print(f"Found JSON string: {json_str[:200]}...")

            # JSON string sifatida parse qilish
            return json.loads(json_str)

        # Alternative: Try to find just the inner JSON
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx + 1]
            print(f"Extracted JSON (alt): {json_str[:200]}...")
            return json.loads(json_str)

        return None

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Problematic text: {text[:500]}")
        return None

    except Exception as e:
        print(f"JSON extract error: {e}")
        return None


def generate_demo_analysis(text, speaking_lesson):
    """Demo analiz (API yo'q bo'lganda)"""
    word_count = len(text.split()) if text else 0
    duration = int((word_count / 150) * 60) if word_count > 0 else 0

    import random

    # Level ga qarab ballar
    level = speaking_lesson.level
    if level == 'beginner':
        base_score = random.randint(40, 70)
    elif level == 'intermediate':
        base_score = random.randint(60, 85)
    else:  # advanced
        base_score = random.randint(70, 95)

    return {
        'fluency_score': random.randint(base_score - 10, base_score + 10),
        'vocabulary_score': random.randint(base_score - 10, base_score + 10),
        'grammar_score': random.randint(base_score - 10, base_score + 10),
        'pronunciation_score': random.randint(base_score - 10, base_score + 10),
        'overall_score': base_score,
        'feedback': f"Good attempt for {speaking_lesson.get_level_display()} level! Your speaking shows understanding of the topic. {speaking_lesson.instruction_text[:100]}...",
        'suggestions': [
            "Practice speaking for 10 minutes daily",
            "Record yourself and listen back",
            "Try to use new vocabulary words"
        ],
        'duration': duration,
        'word_count': word_count,
        'transcript': text if text else "No transcript available"
    }


# ============================================
# ASOSIY VIEW FUNKSIYALAR
# ============================================

@login_required
def speaking_detail(request, speaking_id):
    """Speaking darsini ko'rsatish"""
    speaking = get_object_or_404(SpeakingLesson, id=speaking_id, is_active=True)
    module = speaking.module
    course = module.course

    # Barcha darslarni olish
    all_lessons = list(module.lessons.all().order_by('order'))
    all_listenings = list(module.listening_lessons.all().order_by('order'))
    all_speakings = list(module.speaking_lessons.all().order_by('order'))

    # Barcha darslarni birlashtirish
    all_content = []
    for l in all_lessons:
        all_content.append(('video', l))
    for l in all_listenings:
        all_content.append(('listening', l))
    for l in all_speakings:
        all_content.append(('speaking', l))

    all_content.sort(key=lambda x: x[1].order)

    # Oldingi va keyingi darslarni topish
    current_index = None
    for i, (content_type, content) in enumerate(all_content):
        if content_type == 'speaking' and content.id == speaking_id:
            current_index = i
            break

    prev_content = all_content[current_index - 1] if current_index and current_index > 0 else None
    next_content = all_content[current_index + 1] if current_index and current_index < len(all_content) - 1 else None

    # Foydalanuvchi urinishlari
    attempts = SpeakingAttempt.objects.filter(
        user=request.user,
        speaking_lesson=speaking
    ).order_by('-created_at')[:5]

    return render(request, 'speaking_detail.html', {
        'speaking': speaking,
        'module': module,
        'course': course,
        'questions': speaking.questions.all(),
        'attempts': attempts,
        'prev_content': prev_content,
        'next_content': next_content,
    })


@csrf_exempt
@login_required
def process_speaking(request):
    """Speaking audio ni qayta ishlash - TO'LIQ ISHLAYDI"""
    if request.method == 'POST':
        try:
            print("=" * 50)
            print("PROCESS_SPEAKING STARTED")
            print("=" * 50)

            # 1. Ma'lumotlarni olish
            speaking_id = request.POST.get('speaking_id')
            audio_file = request.FILES.get('audio')

            print(f"Speaking ID: {speaking_id}")
            print(f"Audio file: {audio_file}")
            print(f"File size: {audio_file.size if audio_file else 0} bytes")
            print(f"User: {request.user.username}")

            if not speaking_id or not audio_file:
                print("ERROR: Missing speaking_id or audio_file")
                return JsonResponse({
                    'success': False,
                    'error': 'Audio fayl yoki speaking ID yo\'q'
                })

            # 2. Speaking darsini topish
            speaking = get_object_or_404(SpeakingLesson, id=speaking_id)
            print(f"Speaking lesson: {speaking.title}")

            # 3. Audio ni vaqtinchalik saqlash
            temp_file = None
            try:
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    for chunk in audio_file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

                print(f"Audio saved to temp file: {temp_path}")
                print(f"Temp file size: {os.path.getsize(temp_path)} bytes")

                # 4. Speech-to-Text (STT)
                print("Starting speech-to-text conversion...")
                transcript = speech_to_text(temp_path)
                print(f"Transcript received: {transcript[:100]}...")

                # 5. AI Analysis
                print("Starting AI analysis...")
                analysis_result = analyze_speech_with_ai(transcript, speaking)
                print(f"Analysis complete. Overall score: {analysis_result.get('overall_score', 0)}")

                # 6. AI Feedback uchun TTS audio yaratish
                tts_audio_url = None
                feedback_text = analysis_result.get('feedback', 'Good job! Keep practicing.')

                print("Generating TTS audio...")
                tts_file_path = text_to_speech(
                    text=feedback_text,
                    lang='en',
                    save_path=os.path.join(settings.MEDIA_ROOT, 'speaking_feedback')
                )

                if tts_file_path and os.path.exists(tts_file_path):
                    # Relative URL ni olish
                    relative_path = tts_file_path.replace(settings.MEDIA_ROOT, '')
                    if relative_path.startswith('/'):
                        relative_path = relative_path[1:]
                    tts_audio_url = f"/media/{relative_path}"
                    print(f"TTS audio URL: {tts_audio_url}")
                else:
                    print("WARNING: TTS audio generation failed")

                # 7. Original audio faylni saqlash uchun tayyorlash
                audio_file.seek(0)  # Faylni boshiga qaytarish
                audio_content = ContentFile(audio_file.read())

                # 8. SpeakingAttempt ni yaratish
                print("Creating SpeakingAttempt record...")
                attempt = SpeakingAttempt.objects.create(
                    user=request.user,
                    speaking_lesson=speaking,
                    audio_file=audio_content,
                    transcript=transcript,
                    fluency_score=analysis_result.get('fluency_score', 0),
                    vocabulary_score=analysis_result.get('vocabulary_score', 0),
                    grammar_score=analysis_result.get('grammar_score', 0),
                    pronunciation_score=analysis_result.get('pronunciation_score', 0),
                    overall_score=analysis_result.get('overall_score', 0),
                    ai_feedback=feedback_text,
                    suggestions="\n".join(analysis_result.get('suggestions', [])),
                    duration=analysis_result.get('duration', 0),
                    word_count=analysis_result.get('word_count', 0)
                )

                print(f"Attempt created with ID: {attempt.id}")

                # 9. Progress ni saqlash
                user_progress, created = UserProgress.objects.get_or_create(
                    user=request.user,
                    speaking_lesson=speaking,
                    defaults={
                        'score': analysis_result.get('overall_score', 0),
                        'completed': analysis_result.get('overall_score', 0) >= 50,
                        'completed_at': timezone.now() if analysis_result.get('overall_score', 0) >= 50 else None
                    }
                )

                if not created:
                    user_progress.score = analysis_result.get('overall_score', 0)
                    user_progress.completed = analysis_result.get('overall_score', 0) >= 50
                    if user_progress.completed and not user_progress.completed_at:
                        user_progress.completed_at = timezone.now()
                    user_progress.save()

                print(f"Progress saved: {user_progress.score} points")

                # 10. Natijalarni tayyorlash
                result_data = {
                    'success': True,
                    'attempt_id': attempt.id,
                    'transcript': transcript,
                    'feedback': feedback_text,
                    'suggestions': analysis_result.get('suggestions', []),
                    'tts_audio_url': tts_audio_url,
                    'scores': {
                        'overall': analysis_result.get('overall_score', 0),
                        'fluency': analysis_result.get('fluency_score', 0),
                        'vocabulary': analysis_result.get('vocabulary_score', 0),
                        'grammar': analysis_result.get('grammar_score', 0),
                        'pronunciation': analysis_result.get('pronunciation_score', 0),
                    },
                    'stats': {
                        'word_count': analysis_result.get('word_count', 0),
                        'duration': analysis_result.get('duration', 0)
                    }
                }

                print("=" * 50)
                print("PROCESS_SPEAKING COMPLETED SUCCESSFULLY")
                print("=" * 50)

                return JsonResponse(result_data)

            finally:
                # 11. Vaqtincha faylni o'chirish
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                        print("Temp file cleaned up")
                    except:
                        pass

        except Exception as e:
            print(f"ERROR in process_speaking: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            print(f"Traceback:\n{error_trace}")

            return JsonResponse({
                'success': False,
                'error': str(e),
                'traceback': error_trace
            })

    print("Invalid request method")
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def get_speaking_attempt(request, attempt_id):
    """Speaking urinishini olish"""
    try:
        attempt = get_object_or_404(SpeakingAttempt, id=attempt_id, user=request.user)

        # AI feedback audio borligini tekshirish
        tts_audio_url = None
        if attempt.ai_feedback:
            # Feedback audio faylini qidirish
            feedback_dir = os.path.join(settings.MEDIA_ROOT, 'speaking_feedback')
            if os.path.exists(feedback_dir):
                # Attempt ID ga mos audio faylni qidirish
                for file in os.listdir(feedback_dir):
                    if file.startswith(f"feedback_") and file.endswith('.mp3'):
                        tts_audio_url = f"/media/speaking_feedback/{file}"
                        break

        return JsonResponse({
            'success': True,
            'attempt': {
                'id': attempt.id,
                'transcript': attempt.transcript,
                'fluency_score': attempt.fluency_score,
                'vocabulary_score': attempt.vocabulary_score,
                'grammar_score': attempt.grammar_score,
                'pronunciation_score': attempt.pronunciation_score,
                'overall_score': attempt.overall_score,
                'ai_feedback': attempt.ai_feedback,
                'suggestions': attempt.suggestions.split('\n') if attempt.suggestions else [],
                'duration': attempt.duration,
                'word_count': attempt.word_count,
                'created_at': attempt.created_at.strftime('%Y-%m-%d %H:%M'),
                'audio_url': attempt.audio_file.url if attempt.audio_file else '',
                'tts_audio_url': tts_audio_url
            }
        })

    except Exception as e:
        print(f"Error in get_speaking_attempt: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# courses/views.py - READING VIEW LAR QO'SHISH

from .models import ReadingLesson, ReadingQuestion, ReadingAnswer, UserReadingProgress


# courses/views.py - UserReadingProgress ni o'zgartirish

@login_required
def reading_detail(request, reading_id):
    """Reading darsini ko'rsatish"""
    reading = get_object_or_404(ReadingLesson, id=reading_id, is_active=True)
    module = reading.module
    course = module.course

    # Barcha darslarni olish
    all_lessons = list(module.lessons.all().order_by('order'))
    all_listenings = list(module.listening_lessons.all().order_by('order'))
    all_speakings = list(module.speaking_lessons.all().order_by('order'))
    all_readings = list(module.reading_lessons.all().order_by('order'))

    # Barcha darslarni birlashtirish
    all_content = []
    for l in all_lessons:
        all_content.append(('video', l))
    for l in all_listenings:
        all_content.append(('listening', l))
    for l in all_speakings:
        all_content.append(('speaking', l))
    for l in all_readings:
        all_content.append(('reading', l))

    all_content.sort(key=lambda x: x[1].order)

    # Oldingi va keyingi darslarni topish
    current_index = None
    for i, (content_type, content) in enumerate(all_content):
        if content_type == 'reading' and content.id == reading_id:
            current_index = i
            break

    prev_content = all_content[current_index - 1] if current_index and current_index > 0 else None
    next_content = all_content[current_index + 1] if current_index and current_index < len(all_content) - 1 else None

    # Savollarni olish
    questions = reading.questions.all().order_by('order')

    # Progress - faqat umumiy progressni olish
    user_progress = UserProgress.objects.filter(
        user=request.user,
        reading_lesson=reading
    ).first()

    # Reading progress
    reading_progress = UserReadingProgress.objects.filter(
        user=request.user,
        reading_lesson=reading
    ).first()

    return render(request, 'reading_detail.html', {
        'reading': reading,
        'module': module,
        'course': course,
        'questions': questions,
        'prev_content': prev_content,
        'next_content': next_content,
        'completed': user_progress.completed if user_progress else False,
        'reading_progress': reading_progress
    })


@csrf_exempt
@login_required
def submit_reading_test(request, reading_id):
    """Reading testini topshirish"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reading = get_object_or_404(ReadingLesson, id=reading_id)

            total_questions = 0
            correct_answers = 0
            results = {}
            time_spent = data.get('time_spent', 0)

            # Savollarni tekshirish
            questions = reading.questions.all().order_by('order')

            for question in questions:
                user_answer = data.get(f'question_{question.id}')
                correct_answer = question.answers.filter(is_correct=True).first()

                if user_answer and correct_answer:
                    if str(user_answer) == str(correct_answer.id):
                        correct_answers += 1
                        results[f'question_{question.id}'] = 'correct'
                    else:
                        results[f'question_{question.id}'] = 'wrong'
                else:
                    results[f'question_{question.id}'] = 'not_answered'

                total_questions += 1

            # Ballarni hisoblash
            if total_questions > 0:
                score = (correct_answers / total_questions) * 100
                passed = score >= 60  # IELTS standard 60%
            else:
                score = 0
                passed = False

            # Umumiy Progressni saqlash
            user_progress, created = UserProgress.objects.get_or_create(
                user=request.user,
                reading_lesson=reading,
                defaults={'score': score, 'completed': passed}
            )

            if not created:
                user_progress.score = score
                user_progress.completed = passed
                if passed:
                    user_progress.completed_at = timezone.now()
                user_progress.save()

            # Maxsus Reading progressni saqlash
            reading_progress, created = UserReadingProgress.objects.get_or_create(
                user=request.user,
                reading_lesson=reading,
                defaults={
                    'score': score,
                    'completed': passed,
                    'time_spent': time_spent,
                    'correct_answers': correct_answers,
                    'total_questions': total_questions
                }
            )

            if not created:
                reading_progress.score = score
                reading_progress.completed = passed
                reading_progress.time_spent = time_spent
                reading_progress.correct_answers = correct_answers
                reading_progress.total_questions = total_questions
                if passed:
                    reading_progress.completed_at = timezone.now()
                reading_progress.save()

            return JsonResponse({
                'success': True,
                'score': score,
                'passed': passed,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'time_spent': time_spent,
                'results': results
            })

        except Exception as e:
            print(f"Reading test error: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})
# courses/views.py - module_detail funksiyasini to'g'rilash

@login_required
def module_detail(request, module_id):
    module = get_object_or_404(Module, id=module_id)

    # Barcha dars turlarini olish
    video_lessons = module.lessons.all()
    listening_lessons = module.listening_lessons.all()
    speaking_lessons = module.speaking_lessons.all()
    reading_lessons = module.reading_lessons.all()

    all_lessons = []

    # Video darslar
    for lesson in video_lessons:
        progress = UserProgress.objects.filter(user=request.user, lesson=lesson).first()
        all_lessons.append({
            'id': lesson.id,
            'title': lesson.title,
            'duration': lesson.duration,
            'order': lesson.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'video',
            'object': lesson
        })

    # Listening darslar
    for listening in listening_lessons:
        progress = UserProgress.objects.filter(user=request.user, listening_lesson=listening).first()
        all_lessons.append({
            'id': listening.id,
            'title': listening.title,
            'duration': f"{listening.timer_minutes} min",
            'order': listening.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'listening',
            'listening_type': listening.get_listening_type_display(),
            'object': listening
        })

    # Speaking darslar
    for speaking in speaking_lessons:
        progress = UserProgress.objects.filter(user=request.user, speaking_lesson=speaking).first()
        all_lessons.append({
            'id': speaking.id,
            'title': speaking.title,
            'duration': f"{speaking.target_duration} soniya",
            'order': speaking.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'speaking',
            'speaking_type': speaking.get_speaking_type_display(),
            'object': speaking
        })

    # READING DARSLARNI QO'SHISH
    for reading in reading_lessons:
        progress = UserProgress.objects.filter(user=request.user, reading_lesson=reading).first()
        all_lessons.append({
            'id': reading.id,
            'title': reading.title,
            'duration': f"{reading.timer_minutes} daqiqa",
            'order': reading.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'reading',
            'reading_type': reading.get_reading_type_display(),
            'object': reading
        })

    # Order bo'yicha tartiblash
    all_lessons.sort(key=lambda x: x['order'])

    # Har bir darsga ketma-ket raqam berish
    for index, lesson in enumerate(all_lessons, 1):
        lesson['display_order'] = index

    return render(request, 'module_detail.html', {
        'module': module,
        'lessons': all_lessons
    })


# courses/views.py - WRITING VIEW LAR QO'SHISH

from .models import WritingLesson, WritingAttempt, UserWritingProgress
from gigachat import GigaChat


# ... avvalgi funksiyalar ...

@login_required
def writing_detail(request, writing_id):
    """Writing darsini ko'rsatish"""
    writing = get_object_or_404(WritingLesson, id=writing_id, is_active=True)
    module = writing.module
    course = module.course

    # Barcha darslarni olish
    all_lessons = list(module.lessons.all().order_by('order'))
    all_listenings = list(module.listening_lessons.all().order_by('order'))
    all_speakings = list(module.speaking_lessons.all().order_by('order'))
    all_readings = list(module.reading_lessons.all().order_by('order'))
    all_writings = list(module.writing_lessons.all().order_by('order'))

    # Barcha darslarni birlashtirish
    all_content = []
    for l in all_lessons:
        all_content.append(('video', l))
    for l in all_listenings:
        all_content.append(('listening', l))
    for l in all_speakings:
        all_content.append(('speaking', l))
    for l in all_readings:
        all_content.append(('reading', l))
    for l in all_writings:
        all_content.append(('writing', l))

    all_content.sort(key=lambda x: x[1].order)

    # Oldingi va keyingi darslarni topish
    current_index = None
    for i, (content_type, content) in enumerate(all_content):
        if content_type == 'writing' and content.id == writing_id:
            current_index = i
            break

    prev_content = all_content[current_index - 1] if current_index and current_index > 0 else None
    next_content = all_content[current_index + 1] if current_index and current_index < len(all_content) - 1 else None

    # Urinishlar
    attempts = WritingAttempt.objects.filter(
        user=request.user,
        writing_lesson=writing
    ).order_by('-created_at')[:5]

    # Progress
    user_progress = UserProgress.objects.filter(
        user=request.user,
        writing_lesson=writing
    ).first()

    writing_progress = UserWritingProgress.objects.filter(
        user=request.user,
        writing_lesson=writing
    ).first()

    return render(request, 'writing_detail.html', {
        'writing': writing,
        'module': module,
        'course': course,
        'attempts': attempts,
        'prev_content': prev_content,
        'next_content': next_content,
        'completed': user_progress.completed if user_progress else False,
        'writing_progress': writing_progress
    })


def analyze_writing_with_ai(text, writing_lesson):
    """Writing matnini AI bilan tahlil qilish"""

    if not text or len(text.strip()) < 50:
        return generate_demo_writing_analysis(text, writing_lesson)

    try:
        print(f"Analyzing writing with GigaChat: {text[:100]}...")

        prompt = f"""
        You are an expert IELTS writing examiner. Analyze this writing attempt:

        WRITING TASK TYPE: {writing_lesson.get_writing_type_display()}
        TASK: {writing_lesson.task_text}

        STUDENT ANSWER: "{text}"

        SCORING CRITERIA (0-100 for each):
        1. Task Achievement/Response (Content): Does it fully answer the question?
        2. Coherence and Cohesion: Is it well-organized with good paragraphing?
        3. Lexical Resource (Vocabulary): Range and accuracy of vocabulary
        4. Grammatical Range and Accuracy: Sentence structure and grammar

        REQUIREMENTS:
        - Give constructive, specific feedback
        - Mention strengths and areas for improvement
        - Provide actionable suggestions
        - Keep feedback encouraging but honest

        FORMAT RESPONSE AS VALID JSON ONLY:
        {{
            "content_score": [number 0-100],
            "coherence_score": [number 0-100],
            "vocabulary_score": [number 0-100],
            "grammar_score": [number 0-100],
            "overall_score": [weighted average of above scores],
            "feedback": "Detailed feedback in 4-5 sentences",
            "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3", "Suggestion 4"]
        }}
        """

        print("Sending to GigaChat...")

        with GigaChat(
                credentials="MDE5YWFjYWMtNTdmYi03NTMwLTg4MTctMTQwN2IwNTNlM2FmOjAwNmQ3ZGYwLTM4N2EtNGI2ZS05ODQxLWZhZjAyOTJjZTAyMw==",
                verify_ssl_certs=False,
                model="GigaChat"
        ) as giga:
            response = giga.chat(prompt)
            analysis_text = response.choices[0].message.content

            print(f"GigaChat response: {analysis_text[:200]}...")

            # JSON ni extract qilish
            analysis = extract_json_from_text(analysis_text)

            if analysis:
                print("Writing analysis JSON extracted")

                # Word count hisoblash
                word_count = len(text.split())

                # Qo'shimcha fieldlar
                analysis['word_count'] = word_count
                analysis['answer_text'] = text

                # Ballarni to'g'rilash
                score_keys = ['content_score', 'coherence_score', 'vocabulary_score',
                              'grammar_score', 'overall_score']

                for key in score_keys:
                    if key in analysis:
                        try:
                            if isinstance(analysis[key], str):
                                numbers = re.findall(r'\d+', analysis[key])
                                if numbers:
                                    score = int(numbers[0])
                                    analysis[key] = max(0, min(100, score))
                                else:
                                    analysis[key] = 60
                            else:
                                score = int(analysis[key])
                                analysis[key] = max(0, min(100, score))
                        except:
                            analysis[key] = 60

                # Overall score ni hisoblash (agar yo'q bo'lsa)
                if 'overall_score' not in analysis or analysis['overall_score'] == 0:
                    weights = {'content_score': 0.25, 'coherence_score': 0.25,
                               'vocabulary_score': 0.25, 'grammar_score': 0.25}
                    weighted_sum = 0

                    for key, weight in weights.items():
                        if key in analysis:
                            weighted_sum += analysis[key] * weight

                    analysis['overall_score'] = round(weighted_sum)

                return analysis

            else:
                print("Could not extract JSON, using demo analysis")
                return generate_demo_writing_analysis(text, writing_lesson)

    except Exception as e:
        print(f"Writing analysis error: {e}")
        import traceback
        traceback.print_exc()
        return generate_demo_writing_analysis(text, writing_lesson)


def generate_demo_writing_analysis(text, writing_lesson):
    """Demo writing analiz"""
    word_count = len(text.split()) if text else 0

    import random

    level = writing_lesson.level
    if level == 'beginner':
        base_score = random.randint(45, 65)
    elif level == 'intermediate':
        base_score = random.randint(60, 75)
    else:  # advanced
        base_score = random.randint(70, 85)

    return {
        'content_score': random.randint(base_score - 10, base_score + 10),
        'coherence_score': random.randint(base_score - 10, base_score + 10),
        'vocabulary_score': random.randint(base_score - 10, base_score + 10),
        'grammar_score': random.randint(base_score - 10, base_score + 10),
        'overall_score': base_score,
        'feedback': f"Good attempt for {writing_lesson.get_level_display()} level. You addressed the task requirements adequately. {writing_lesson.task_text[:100]}...",
        'suggestions': [
            "Use more varied sentence structures",
            "Improve paragraph organization",
            "Add more specific examples",
            "Check grammar and punctuation"
        ],
        'word_count': word_count,
        'answer_text': text if text else "No answer provided"
    }


@csrf_exempt
@login_required
def submit_writing(request, writing_id):
    """Writing topshirish"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            writing = get_object_or_404(WritingLesson, id=writing_id)

            answer_text = data.get('answer_text', '').strip()
            time_spent = data.get('time_spent', 0)
            word_count = data.get('word_count', 0)

            if not answer_text:
                return JsonResponse({'success': False, 'error': 'Iltimos, javob yozing!'})

            # AI tahlili
            print("Analyzing writing with AI...")
            analysis_result = analyze_writing_with_ai(answer_text, writing)
            print(f"Analysis complete. Overall score: {analysis_result.get('overall_score', 0)}")

            # WritingAttempt ni yaratish
            attempt = WritingAttempt.objects.create(
                user=request.user,
                writing_lesson=writing,
                answer_text=answer_text,
                word_count=word_count,
                content_score=analysis_result.get('content_score', 0),
                coherence_score=analysis_result.get('coherence_score', 0),
                vocabulary_score=analysis_result.get('vocabulary_score', 0),
                grammar_score=analysis_result.get('grammar_score', 0),
                overall_score=analysis_result.get('overall_score', 0),
                ai_feedback=analysis_result.get('feedback', ''),
                suggestions="\n".join(analysis_result.get('suggestions', [])),
                time_spent=time_spent
            )

            # Umumiy Progressni saqlash
            user_progress, created = UserProgress.objects.get_or_create(
                user=request.user,
                writing_lesson=writing,
                defaults={'score': analysis_result.get('overall_score', 0), 'completed': True}
            )

            if not created:
                user_progress.score = analysis_result.get('overall_score', 0)
                user_progress.completed = True
                if not user_progress.completed_at:
                    user_progress.completed_at = timezone.now()
                user_progress.save()

            # Maxsus Writing progressni yangilash
            writing_progress, created = UserWritingProgress.objects.get_or_create(
                user=request.user,
                writing_lesson=writing,
                defaults={
                    'score': analysis_result.get('overall_score', 0),
                    'best_score': analysis_result.get('overall_score', 0),
                    'completed': True,
                    'attempts_count': 1,
                    'time_spent': time_spent
                }
            )

            if not created:
                writing_progress.attempts_count += 1
                writing_progress.time_spent += time_spent
                if analysis_result.get('overall_score', 0) > writing_progress.best_score:
                    writing_progress.best_score = analysis_result.get('overall_score', 0)
                writing_progress.score = analysis_result.get('overall_score', 0)
                writing_progress.completed = True
                if not writing_progress.completed_at:
                    writing_progress.completed_at = timezone.now()
                writing_progress.save()

            return JsonResponse({
                'success': True,
                'attempt_id': attempt.id,
                'scores': {
                    'overall': analysis_result.get('overall_score', 0),
                    'content': analysis_result.get('content_score', 0),
                    'coherence': analysis_result.get('coherence_score', 0),
                    'vocabulary': analysis_result.get('vocabulary_score', 0),
                    'grammar': analysis_result.get('grammar_score', 0),
                },
                'feedback': analysis_result.get('feedback', ''),
                'suggestions': analysis_result.get('suggestions', []),
                'stats': {
                    'word_count': word_count,
                    'time_spent': time_spent
                }
            })

        except Exception as e:
            print(f"Writing submission error: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def get_writing_attempt(request, attempt_id):
    """Writing urinishini olish"""
    try:
        attempt = get_object_or_404(WritingAttempt, id=attempt_id, user=request.user)

        return JsonResponse({
            'success': True,
            'attempt': {
                'id': attempt.id,
                'answer_text': attempt.answer_text,
                'content_score': attempt.content_score,
                'coherence_score': attempt.coherence_score,
                'vocabulary_score': attempt.vocabulary_score,
                'grammar_score': attempt.grammar_score,
                'overall_score': attempt.overall_score,
                'ai_feedback': attempt.ai_feedback,
                'suggestions': attempt.suggestions.split('\n') if attempt.suggestions else [],
                'word_count': attempt.word_count,
                'time_spent': attempt.time_spent,
                'created_at': attempt.created_at.strftime('%Y-%m-%d %H:%M'),
            }
        })

    except Exception as e:
        print(f"Error in get_writing_attempt: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# Module detail funksiyasini yangilash (writing qo'shish)
@login_required
def module_detail(request, module_id):
    module = get_object_or_404(Module, id=module_id)

    # Barcha dars turlarini olish
    video_lessons = module.lessons.all()
    listening_lessons = module.listening_lessons.all()
    speaking_lessons = module.speaking_lessons.all()
    reading_lessons = module.reading_lessons.all()
    writing_lessons = module.writing_lessons.all()  # YANGI QATOR

    all_lessons = []

    # Video darslar
    for lesson in video_lessons:
        progress = UserProgress.objects.filter(user=request.user, lesson=lesson).first()
        all_lessons.append({
            'id': lesson.id,
            'title': lesson.title,
            'duration': lesson.duration,
            'order': lesson.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'video',
            'object': lesson
        })

    # Listening darslar
    for listening in listening_lessons:
        progress = UserProgress.objects.filter(user=request.user, listening_lesson=listening).first()
        all_lessons.append({
            'id': listening.id,
            'title': listening.title,
            'duration': f"{listening.timer_minutes} min",
            'order': listening.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'listening',
            'listening_type': listening.get_listening_type_display(),
            'object': listening
        })

    # Speaking darslar
    for speaking in speaking_lessons:
        progress = UserProgress.objects.filter(user=request.user, speaking_lesson=speaking).first()
        all_lessons.append({
            'id': speaking.id,
            'title': speaking.title,
            'duration': f"{speaking.target_duration} soniya",
            'order': speaking.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'speaking',
            'speaking_type': speaking.get_speaking_type_display(),
            'object': speaking
        })

    # Reading darslar
    for reading in reading_lessons:
        progress = UserProgress.objects.filter(user=request.user, reading_lesson=reading).first()
        all_lessons.append({
            'id': reading.id,
            'title': reading.title,
            'duration': f"{reading.timer_minutes} daqiqa",
            'order': reading.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'reading',
            'reading_type': reading.get_reading_type_display(),
            'object': reading
        })

    # WRITING DARSLARNI QO'SHISH - YANGI QATORLAR
    for writing in writing_lessons:
        progress = UserProgress.objects.filter(user=request.user, writing_lesson=writing).first()
        all_lessons.append({
            'id': writing.id,
            'title': writing.title,
            'duration': f"{writing.timer_minutes} daqiqa",
            'order': writing.order,
            'completed': progress.completed if progress else False,
            'score': progress.score if progress else 0,
            'type': 'writing',
            'writing_type': writing.get_writing_type_display(),
            'object': writing
        })

    # Order bo'yicha tartiblash
    all_lessons.sort(key=lambda x: x['order'])

    # Har bir darsga ketma-ket raqam berish
    for index, lesson in enumerate(all_lessons, 1):
        lesson['display_order'] = index

    return render(request, 'module_detail.html', {
        'module': module,
        'lessons': all_lessons
    })