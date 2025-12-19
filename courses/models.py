from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator

def lesson_video_upload_path(instance, filename):
    """Video fayl uchun yo'l yaratish"""
    timestamp = int(timezone.now().timestamp())
    ext = filename.split('.')[-1]
    filename = f"course_{instance.module.course.id}_module_{instance.module.id}_lesson_{instance.id}_{timestamp}.{ext}"
    return f'lesson_videos/{filename}'


def listening_audio_upload_path(instance, filename):
    """Audio fayl uchun yo'l yaratish"""
    timestamp = int(timezone.now().timestamp())
    ext = filename.split('.')[-1]
    filename = f"course_{instance.module.course.id}_module_{instance.module.id}_listening_{instance.id}_{timestamp}.{ext}"
    return f'listening_audios/{filename}'


# 1. AVVAL Course MODELI
class Course(models.Model):
    COURSE_TYPES = [
        ('english', 'Ingliz tili'),
        ('data_science', 'Data Science va Sun\'iy Intellekt'),
        ('pedagogy', 'Pedagogika'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField()
    course_type = models.CharField(max_length=50, choices=COURSE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# 2. KEYIN Module MODELI
class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.name} - {self.title}"


# 3. KEYIN Lesson MODELI (Module dan keyin)
class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)

    # Video fayl va URL
    video_file = models.FileField(upload_to=lesson_video_upload_path, blank=True, null=True,
                                  verbose_name="Video fayl")
    video_url = models.URLField(blank=True, verbose_name="YouTube linki")

    content = models.TextField(blank=True)
    duration = models.CharField(max_length=50, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} - {self.title}"

    def get_video_source(self):
        """Video manbasini qaytarish"""
        if self.video_file:
            return self.video_file.url
        elif self.video_url:
            return self.video_url
        return None

    def video_type(self):
        """Video turini aniqlash"""
        if self.video_file:
            return 'file'
        elif self.video_url:
            if 'youtube.com' in self.video_url or 'youtu.be' in self.video_url:
                return 'youtube'
            return 'external'
        return None


# 4. LISTENING LESSON MODELI (Lesson dan keyin, Question dan oldin)
class ListeningLesson(models.Model):
    LISTENING_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('matching', 'Matching'),
        ('gap_filling', 'Gap Filling'),
        ('true_false_not_given', 'True/False/Not Given'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='listening_lessons')
    title = models.CharField(max_length=200)
    order = models.IntegerField(default=0)
    audio_file = models.FileField(upload_to=listening_audio_upload_path, verbose_name="Audio fayl")
    listening_type = models.CharField(max_length=50, choices=LISTENING_TYPES)
    description = models.TextField(blank=True, help_text="Listening mazmuni, ko'rsatmalar")
    timer_minutes = models.IntegerField(default=0, help_text="0 yozilsa timer ishlamaydi")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Listening darsi"
        verbose_name_plural = "Listening darslari"

    def __str__(self):
        return f"{self.module.title} - {self.title} ({self.get_listening_type_display()})"


# 5. Yangi model: ListeningQuestion (Listening uchun savollar)
class ListeningQuestion(models.Model):
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.listening_lesson.title} - Savol {self.order}"


# 6. Yangi model: ListeningOption (Listening uchun variantlar)
class ListeningOption(models.Model):
    question = models.ForeignKey(ListeningQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    option_letter = models.CharField(max_length=2, default='A')  # A, B, C, D

    class Meta:
        ordering = ['option_letter']

    def __str__(self):
        return f"{self.question.question_text[:30]}... - {self.option_letter}) {self.option_text[:30]}..."


# 7. Yangi model: GapFillingQuestion (Gap filling uchun maxsus)
class GapFillingQuestion(models.Model):
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE, related_name='gap_fillings')
    text_with_gaps = models.TextField(help_text="Matn bo'sh joylar bilan: (a) ______")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Gap filling: {self.text_with_gaps[:50]}..."


# 8. Yangi model: GapOption (Gap uchun variantlar)
class GapOption(models.Model):
    gap_filling = models.ForeignKey(GapFillingQuestion, on_delete=models.CASCADE, related_name='options')
    gap_letter = models.CharField(max_length=2)  # a, b, c, d
    correct_word = models.CharField(max_length=200)
    options = models.TextField(help_text="Variantlar vergul bilan ajratilgan: goes,went,was going,is going")

    class Meta:
        ordering = ['gap_letter']

    def __str__(self):
        return f"Gap {self.gap_letter}: {self.correct_word}"


# 9. Question MODELI (avvalgi Question)
class Question(models.Model):
    QUESTION_TYPES = [
        ('single', 'Bitta to\'g\'ri javob'),
        ('multiple', 'Bir nechta to\'g\'ri javob'),
        ('text', 'Matnli javob'),
    ]

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lesson.title} - {self.question_text[:50]}..."


# 10. Answer MODELI (avvalgi Answer)
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.answer_text[:50]}..."


# 11. Yangi model: TrueFalseNotGiven (TFNG uchun)
class TrueFalseNotGiven(models.Model):
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE, related_name='tfng_questions')
    statement = models.TextField()
    correct_answer = models.CharField(max_length=20, choices=[
        ('true', 'True'),
        ('false', 'False'),
        ('not_given', 'Not Given')
    ])
    explanation = models.TextField(blank=True, help_text="Javob tushuntirishi")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"TFNG: {self.statement[:50]}..."


# 12. Yangi model: MatchingQuestion (Matching uchun)
class MatchingQuestion(models.Model):
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE, related_name='matching_questions')
    title = models.CharField(max_length=200)
    instruction = models.TextField()
    column_a = models.TextField(help_text="Birinchi ustun elementlari, qatorlar bilan ajratilgan")
    column_b = models.TextField(help_text="Ikkinchi ustun elementlari, qatorlar bilan ajratilgan")
    correct_matches = models.TextField(help_text="To'g'ri moslamalar JSON formatda: {'1':'A','2':'B'}")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Matching: {self.title}"


def speaking_audio_upload_path(instance, filename):
    """Speaking audio fayl uchun yo'l"""
    timestamp = int(timezone.now().timestamp())
    ext = filename.split('.')[-1]
    unique_id = str(uuid.uuid4())[:8]
    return f'speaking_audio/user_{instance.user.id}/{timestamp}_{unique_id}.{ext}'


class SpeakingLesson(models.Model):
    """Speaking darslari"""
    SPEAKING_TYPES = [
        ('question_answer', 'Savol-Javob'),
        ('topic_discussion', 'Mavzu bo\'yicha nutq'),
        ('role_play', 'Role Play'),
        ('picture_description', 'Rasm tasviri'),
        ('story_telling', 'Hikoya qilish'),
    ]

    LEVELS = [
        ('beginner', 'Boshlang\'ich'),
        ('intermediate', 'O\'rta'),
        ('advanced', 'Yuqori'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='speaking_lessons')
    title = models.CharField(max_length=200)
    description = models.TextField()
    speaking_type = models.CharField(max_length=50, choices=SPEAKING_TYPES)
    level = models.CharField(max_length=20, choices=LEVELS, default='beginner')
    instruction_text = models.TextField(help_text="Studentga ko'rsatma")
    example_text = models.TextField(blank=True, help_text="Namuna javob")
    target_duration = models.IntegerField(default=60, help_text="Maqsadli davomiylik (soniya)")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Speaking darsi"
        verbose_name_plural = "Speaking darslari"

    def __str__(self):
        return f"{self.title} ({self.get_level_display()})"


class SpeakingQuestion(models.Model):
    """Speaking uchun savollar"""
    speaking_lesson = models.ForeignKey(SpeakingLesson, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    hints = models.TextField(blank=True, help_text="Yordamchi so'zlar/iboralar")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.speaking_lesson.title} - Savol {self.order}"


class SpeakingAttempt(models.Model):
    """Speaking urinishlari"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='speaking_attempts')
    speaking_lesson = models.ForeignKey(SpeakingLesson, on_delete=models.CASCADE, related_name='attempts')
    audio_file = models.FileField(upload_to=speaking_audio_upload_path, verbose_name="Audio fayl")
    transcript = models.TextField(blank=True, help_text="STT natijasi")
    fluency_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    vocabulary_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    grammar_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    pronunciation_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    overall_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    ai_feedback = models.TextField(blank=True, help_text="AI tahlili")
    suggestions = models.TextField(blank=True, help_text="Takliflar")
    duration = models.IntegerField(default=0, help_text="Davomiylik (soniya)")
    word_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.speaking_lesson.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# 13. UserProgress MODELI (TO'G'RILANGAN VERSIYA)
class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress', null=True, blank=True)
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE,
                                         related_name='user_progress', null=True, blank=True)
    speaking_lesson = models.ForeignKey(SpeakingLesson, on_delete=models.CASCADE,  # ← YANGI QATOR
                                        related_name='user_progress', null=True, blank=True)
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ['user', 'lesson'],
            ['user', 'listening_lesson'],
            ['user', 'speaking_lesson']  # ← speaking_lesson maydoni e'lon qilinganidan keyin
        ]

    def __str__(self):
        if self.lesson:
            return f"{self.user.username} - {self.lesson.title}"
        elif self.listening_lesson:
            return f"{self.user.username} - {self.listening_lesson.title} (Listening)"
        elif self.speaking_lesson:
            return f"{self.user.username} - {self.speaking_lesson.title} (Speaking)"
        return f"{self.user.username} - Progress"


# 14. UserQuestion MODELI
class UserQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions_asked')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_questions')
    question_text = models.TextField()
    is_answered = models.BooleanField(default=False)
    answer_text = models.TextField(blank=True)
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}: {self.question_text[:50]}..."


# courses/models.py - TO'G'RILANGAN VERSIYA

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator


# ... (upload path funksiyalari avvalgidek) ...

# READING MODELI QO'SHISH

def reading_image_upload_path(instance, filename):
    """Reading uchun rasm fayl yo'li"""
    timestamp = int(timezone.now().timestamp())
    ext = filename.split('.')[-1]
    return f'reading_images/{instance.id}_{timestamp}.{ext}'


class ReadingLesson(models.Model):
    """IELTS style Reading darslari"""
    READING_TYPES = [
        ('sentence_completion', 'Sentence Completion'),
        ('matching_headings', 'Matching Headings'),
        ('short_answer', 'Short-Answer Questions'),
        ('true_false_not_given', 'True/False/Not Given'),
        ('yes_no_not_given', 'Yes/No/Not Given'),
        ('multiple_choice', 'Multiple Choice'),
        ('diagram_completion', 'Diagram/Flow-chart/Table Completion'),
        ('summary_completion', 'Summary Completion'),
    ]

    LEVELS = [
        ('beginner', 'Birinchi (4.0-5.0)'),
        ('intermediate', 'Ikkinchi (5.0-6.0)'),
        ('advanced', 'Uchinchi (6.0-7.5)'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='reading_lessons')
    title = models.CharField(max_length=200)
    reading_type = models.CharField(max_length=50, choices=READING_TYPES)
    level = models.CharField(max_length=20, choices=LEVELS, default='beginner')
    description = models.TextField(help_text="Reading matni yoki ko'rsatmalar")
    reading_text = models.TextField(help_text="Asosiy reading matni")
    instruction = models.TextField(help_text="Talaba uchun ko'rsatmalar")
    diagram_image = models.ImageField(upload_to=reading_image_upload_path, blank=True, null=True,
                                      verbose_name="Diagramma/rasm")
    timer_minutes = models.IntegerField(default=20, help_text="Vaqt chegarasi (daqiqa)")
    word_count = models.IntegerField(default=0, help_text="Matndagi so'zlar soni")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Reading darsi"
        verbose_name_plural = "Reading darslari"

    def __str__(self):
        return f"{self.title} ({self.get_reading_type_display()})"


class ReadingQuestion(models.Model):
    """Reading savollari"""
    reading_lesson = models.ForeignKey(ReadingLesson, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=50, choices=ReadingLesson.READING_TYPES)
    marks = models.IntegerField(default=1, help_text="Ball")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class ReadingAnswer(models.Model):
    """Reading javoblari"""
    question = models.ForeignKey(ReadingQuestion, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    explanation = models.TextField(blank=True, help_text="Javob tushuntirishi")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.answer_text[:50]}..."


class UserReadingProgress(models.Model):
    """Foydalanuvchi reading progressi"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reading_progress')
    reading_lesson = models.ForeignKey(ReadingLesson, on_delete=models.CASCADE,
                                       related_name='reading_user_progress')  # O'ZGARDI: related_name
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    time_spent = models.IntegerField(default=0, help_text="Sarflangan vaqt (soniya)")
    correct_answers = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'reading_lesson']
        verbose_name = "Reading progress"
        verbose_name_plural = "Reading progresslar"

    def __str__(self):
        return f"{self.user.username} - {self.reading_lesson.title} - {self.score}%"


# UserProgress modelini yangilash
class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE,
                               related_name='user_progress', null=True, blank=True)
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE,
                                         related_name='user_progress', null=True, blank=True)
    speaking_lesson = models.ForeignKey(SpeakingLesson, on_delete=models.CASCADE,
                                        related_name='user_progress', null=True, blank=True)
    reading_lesson = models.ForeignKey(ReadingLesson, on_delete=models.CASCADE,
                                       related_name='general_user_progress', null=True,
                                       blank=True)  # O'ZGARDI: related_name
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ['user', 'lesson'],
            ['user', 'listening_lesson'],
            ['user', 'speaking_lesson'],
            ['user', 'reading_lesson']
        ]

    def __str__(self):
        if self.lesson:
            return f"{self.user.username} - {self.lesson.title}"
        elif self.listening_lesson:
            return f"{self.user.username} - {self.listening_lesson.title} (Listening)"
        elif self.speaking_lesson:
            return f"{self.user.username} - {self.speaking_lesson.title} (Speaking)"
        elif self.reading_lesson:
            return f"{self.user.username} - {self.reading_lesson.title} (Reading)"
        return f"{self.user.username} - Progress"


# courses/models.py - WRITING MODELI QO'SHISH

def writing_image_upload_path(instance, filename):
    """Writing uchun rasm fayl yo'li"""
    timestamp = int(timezone.now().timestamp())
    ext = filename.split('.')[-1]
    return f'writing_images/{instance.id}_{timestamp}.{ext}'


class WritingLesson(models.Model):
    """IELTS style Writing darslari"""
    WRITING_TYPES = [
        ('task1_academic', 'Task 1 (Academic)'),
        ('task1_general', 'Task 1 (General)'),
        ('task2', 'Task 2'),
        ('essay', 'Essay'),
        ('letter', 'Letter'),
        ('report', 'Report'),
    ]

    WRITING_TASK_TYPES = [
        ('opinion', 'Opinion Essay'),
        ('discussion', 'Discussion Essay'),
        ('problem_solution', 'Problem-Solution'),
        ('advantages_disadvantages', 'Advantages-Disadvantages'),
        ('two_part', 'Two-part Question'),
    ]

    LEVELS = [
        ('beginner', 'Birinchi (4.0-5.0)'),
        ('intermediate', 'Ikkinchi (5.0-6.0)'),
        ('advanced', 'Uchinchi (6.0-7.5)'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='writing_lessons')
    title = models.CharField(max_length=200)
    writing_type = models.CharField(max_length=50, choices=WRITING_TYPES)
    task_type = models.CharField(max_length=50, choices=WRITING_TASK_TYPES, blank=True)
    level = models.CharField(max_length=20, choices=LEVELS, default='beginner')
    description = models.TextField(help_text="Writing vazifasi haqida ma'lumot")
    task_text = models.TextField(help_text="Writing vazifa matni")
    instruction = models.TextField(help_text="Talaba uchun ko'rsatmalar")
    example_image = models.ImageField(upload_to=writing_image_upload_path, blank=True, null=True,
                                      verbose_name="Namuna diagramma/rasm")
    word_count_min = models.IntegerField(default=150, help_text="Minimal so'zlar soni")
    word_count_max = models.IntegerField(default=250, help_text="Maksimal so'zlar soni")
    timer_minutes = models.IntegerField(default=60, help_text="Vaqt chegarasi (daqiqa)")
    criteria_content = models.IntegerField(default=25, help_text="Content uchun ball (0-100)")
    criteria_coherence = models.IntegerField(default=25, help_text="Coherence uchun ball (0-100)")
    criteria_vocabulary = models.IntegerField(default=25, help_text="Vocabulary uchun ball (0-100)")
    criteria_grammar = models.IntegerField(default=25, help_text="Grammar uchun ball (0-100)")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Writing darsi"
        verbose_name_plural = "Writing darslari"

    def __str__(self):
        return f"{self.title} ({self.get_writing_type_display()})"


class WritingAttempt(models.Model):
    """Foydalanuvchi writing urinishlari"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='writing_attempts')
    writing_lesson = models.ForeignKey(WritingLesson, on_delete=models.CASCADE, related_name='attempts')
    answer_text = models.TextField(help_text="Foydalanuvchi javobi")
    word_count = models.IntegerField(default=0)
    content_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    coherence_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    vocabulary_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    grammar_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    overall_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    ai_feedback = models.TextField(blank=True, help_text="AI tahlili")
    suggestions = models.TextField(blank=True, help_text="Takliflar")
    time_spent = models.IntegerField(default=0, help_text="Sarflangan vaqt (soniya)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.writing_lesson.title} - {self.overall_score}"


class UserWritingProgress(models.Model):
    """Foydalanuvchi writing progressi"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='writing_progress')
    writing_lesson = models.ForeignKey(WritingLesson, on_delete=models.CASCADE,
                                       related_name='writing_user_progress')
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    best_score = models.FloatField(default=0)
    attempts_count = models.IntegerField(default=0)
    time_spent = models.IntegerField(default=0, help_text="Jami sarflangan vaqt (soniya)")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'writing_lesson']
        verbose_name = "Writing progress"
        verbose_name_plural = "Writing progresslar"

    def __str__(self):
        return f"{self.user.username} - {self.writing_lesson.title} - {self.score}%"


# UserProgress modeliga writing_lesson qo'shish
class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE,
                               related_name='user_progress', null=True, blank=True)
    listening_lesson = models.ForeignKey(ListeningLesson, on_delete=models.CASCADE,
                                         related_name='user_progress', null=True, blank=True)
    speaking_lesson = models.ForeignKey(SpeakingLesson, on_delete=models.CASCADE,
                                        related_name='user_progress', null=True, blank=True)
    reading_lesson = models.ForeignKey(ReadingLesson, on_delete=models.CASCADE,
                                       related_name='general_user_progress', null=True, blank=True)
    writing_lesson = models.ForeignKey(WritingLesson, on_delete=models.CASCADE,  # YANGI QATOR
                                       related_name='general_user_progress', null=True, blank=True)
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ['user', 'lesson'],
            ['user', 'listening_lesson'],
            ['user', 'speaking_lesson'],
            ['user', 'reading_lesson'],
            ['user', 'writing_lesson']  # YANGI QATOR
        ]

    def __str__(self):
        if self.lesson:
            return f"{self.user.username} - {self.lesson.title}"
        elif self.listening_lesson:
            return f"{self.user.username} - {self.listening_lesson.title} (Listening)"
        elif self.speaking_lesson:
            return f"{self.user.username} - {self.speaking_lesson.title} (Speaking)"
        elif self.reading_lesson:
            return f"{self.user.username} - {self.reading_lesson.title} (Reading)"
        elif self.writing_lesson:
            return f"{self.user.username} - {self.writing_lesson.title} (Writing)"
        return f"{self.user.username} - Progress"