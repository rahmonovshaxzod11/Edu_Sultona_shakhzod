# admin.py faylini to'g'rilaymiz

from django.contrib import admin
from .models import Course, Module, Lesson, Question, Answer, UserProgress, UserQuestion, ListeningLesson, \
    ListeningQuestion, ListeningOption, GapFillingQuestion, GapOption, TrueFalseNotGiven, MatchingQuestion, SpeakingLesson, SpeakingQuestion, SpeakingAttempt,ReadingLesson, ReadingQuestion, ReadingAnswer, UserReadingProgress
from django.utils.html import format_html


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_type', 'is_active', 'created_at')
    list_filter = ('course_type', 'is_active')
    search_fields = ('name', 'description')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'description')


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerInline]
    list_display = ('question_text', 'lesson', 'question_type')
    list_filter = ('lesson__module__course', 'question_type')
    search_fields = ('question_text',)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order', 'duration', 'video_type_display', 'video_preview')
    list_filter = ('module__course', 'module')
    search_fields = ('title', 'content')

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('module', 'title', 'content', 'duration', 'order')
        }),
        ('Video', {
            'fields': ('video_file', 'video_url'),
            'description': 'Video fayl yoki YouTube linkini qo\'ying. Agar ikkalasi ham bo\'lsa, fayl ustunlik qiladi.'
        }),
    )

    def video_type_display(self, obj):
        """Video turini ko'rsatish"""
        video_type = obj.video_type()
        if video_type == 'file':
            return format_html('<span style="color: green;">📁 Lokal video</span>')
        elif video_type == 'youtube':
            return format_html('<span style="color: red;">▶️ YouTube</span>')
        elif video_type == 'external':
            return format_html('<span style="color: blue;">🔗 Tashqi havola</span>')
        return format_html('<span style="color: gray;">❌ Video yo\'q</span>')

    video_type_display.short_description = 'Video turi'

    def video_preview(self, obj):
        """Video manbasini ko'rsatish"""
        if obj.video_file:
            return format_html(f'<a href="{obj.video_file.url}" target="_blank">📁 Faylni ko\'rish</a>')
        elif obj.video_url:
            return format_html(f'<a href="{obj.video_url}" target="_blank">🔗 Havolani ochish</a>')
        return "—"

    video_preview.short_description = 'Video manbasi'


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'completed', 'score', 'completed_at')
    list_filter = ('completed', 'lesson__module__course')
    search_fields = ('user__username', 'lesson__title')


@admin.register(UserQuestion)
class UserQuestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'question_text', 'is_answered', 'asked_at')
    list_filter = ('is_answered', 'lesson__module__course')
    search_fields = ('user__username', 'question_text', 'answer_text')


# LISTENING ADMIN CLASSES

class ListeningOptionInline(admin.TabularInline):
    model = ListeningOption
    extra = 4


@admin.register(ListeningQuestion)
class ListeningQuestionAdmin(admin.ModelAdmin):
    inlines = [ListeningOptionInline]
    list_display = ('question_text', 'listening_lesson', 'order')
    list_filter = ('listening_lesson__module__course', 'listening_lesson')
    ordering = ('listening_lesson', 'order')


class GapOptionInline(admin.TabularInline):
    model = GapOption
    extra = 1


@admin.register(GapFillingQuestion)
class GapFillingQuestionAdmin(admin.ModelAdmin):
    inlines = [GapOptionInline]
    list_display = ('listening_lesson', 'order')
    list_filter = ('listening_lesson__module__course', 'listening_lesson')


@admin.register(TrueFalseNotGiven)
class TrueFalseNotGivenAdmin(admin.ModelAdmin):
    list_display = ('statement', 'listening_lesson', 'correct_answer', 'order')
    list_filter = ('listening_lesson__module__course', 'listening_lesson', 'correct_answer')
    ordering = ('listening_lesson', 'order')


@admin.register(MatchingQuestion)
class MatchingQuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'listening_lesson', 'order')
    list_filter = ('listening_lesson__module__course', 'listening_lesson')
    ordering = ('listening_lesson', 'order')


# SPEAKING ADMIN CLASSES

class SpeakingQuestionInline(admin.TabularInline):
    model = SpeakingQuestion
    extra = 1


@admin.register(SpeakingLesson)
class SpeakingLessonAdmin(admin.ModelAdmin):
    inlines = [SpeakingQuestionInline]
    list_display = ('title', 'module', 'speaking_type', 'level', 'order', 'is_active')
    list_filter = ('module__course', 'module', 'speaking_type', 'level', 'is_active')
    search_fields = ('title', 'description')
    ordering = ('module', 'order')

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('module', 'title', 'speaking_type', 'level', 'order', 'is_active')
        }),
        ('Kontent', {
            'fields': ('description', 'instruction_text', 'example_text', 'target_duration')
        }),
    )


@admin.register(SpeakingAttempt)
class SpeakingAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'speaking_lesson', 'overall_score', 'duration', 'created_at')
    list_filter = ('speaking_lesson__module__course', 'speaking_lesson', 'created_at')
    search_fields = ('user__username', 'speaking_lesson__title', 'transcript')
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('user', 'speaking_lesson', 'audio_file', 'duration', 'word_count', 'created_at')
        }),
        ('Transkript', {
            'fields': ('transcript',)
        }),
        ('Baholar', {
            'fields': ('fluency_score', 'vocabulary_score', 'grammar_score', 'pronunciation_score', 'overall_score')
        }),
        ('Tahlil', {
            'fields': ('ai_feedback', 'suggestions')
        }),
    )

class ReadingAnswerInline(admin.TabularInline):
    model = ReadingAnswer
    extra = 4


@admin.register(ReadingQuestion)
class ReadingQuestionAdmin(admin.ModelAdmin):
    inlines = [ReadingAnswerInline]
    list_display = ('question_text', 'reading_lesson', 'question_type', 'order')
    list_filter = ('reading_lesson__module__course', 'reading_lesson', 'question_type')
    ordering = ('reading_lesson', 'order')


@admin.register(ReadingLesson)
class ReadingLessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'reading_type', 'level', 'order', 'is_active', 'diagram_preview')
    list_filter = ('module__course', 'module', 'reading_type', 'level', 'is_active')
    search_fields = ('title', 'description', 'reading_text')
    ordering = ('module', 'order')

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('module', 'title', 'reading_type', 'level', 'order', 'is_active')
        }),
        ('Kontent', {
            'fields': ('description', 'reading_text', 'instruction', 'diagram_image')
        }),
        ('Vaqt va so\'zlar', {
            'fields': ('timer_minutes', 'word_count')
        }),
    )

    def diagram_preview(self, obj):
        if obj.diagram_image:
            return format_html(
                f'<img src="{obj.diagram_image.url}" style="width: 50px; height: 50px; object-fit: cover;" />')
        return "—"

    diagram_preview.short_description = 'Diagramma'


@admin.register(UserReadingProgress)
class UserReadingProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'reading_lesson', 'score', 'completed', 'time_spent', 'completed_at')
    list_filter = ('completed', 'reading_lesson__module__course')
    search_fields = ('user__username', 'reading_lesson__title')


# courses/admin.py - WRITING ADMIN QO'SHISH

from .models import WritingLesson, WritingAttempt, UserWritingProgress
from django.utils.html import format_html


# ... avvalgi adminlar ...

@admin.register(WritingAttempt)
class WritingAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'writing_lesson', 'overall_score', 'word_count', 'created_at')
    list_filter = ('writing_lesson__module__course', 'writing_lesson', 'created_at')
    search_fields = ('user__username', 'writing_lesson__title', 'answer_text')
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('user', 'writing_lesson', 'answer_text', 'word_count', 'time_spent', 'created_at')
        }),
        ('Baholar', {
            'fields': ('content_score', 'coherence_score', 'vocabulary_score', 'grammar_score', 'overall_score')
        }),
        ('Tahlil', {
            'fields': ('ai_feedback', 'suggestions')
        }),
    )


@admin.register(WritingLesson)
class WritingLessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'writing_type', 'task_type', 'level', 'order', 'is_active', 'example_preview')
    list_filter = ('module__course', 'module', 'writing_type', 'task_type', 'level', 'is_active')
    search_fields = ('title', 'description', 'task_text')
    ordering = ('module', 'order')

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('module', 'title', 'writing_type', 'task_type', 'level', 'order', 'is_active')
        }),
        ('Kontent', {
            'fields': ('description', 'task_text', 'instruction', 'example_image')
        }),
        ('So\'zlar va vaqt', {
            'fields': ('word_count_min', 'word_count_max', 'timer_minutes')
        }),
        ('Baholash mezonlari', {
            'fields': ('criteria_content', 'criteria_coherence', 'criteria_vocabulary', 'criteria_grammar')
        }),
    )

    def example_preview(self, obj):
        if obj.example_image:
            return format_html(
                f'<img src="{obj.example_image.url}" style="width: 50px; height: 50px; object-fit: cover;" />')
        return "—"

    example_preview.short_description = 'Namuna'


@admin.register(UserWritingProgress)
class UserWritingProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'writing_lesson', 'score', 'best_score', 'completed', 'attempts_count', 'completed_at')
    list_filter = ('completed', 'writing_lesson__module__course')
    search_fields = ('user__username', 'writing_lesson__title')