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