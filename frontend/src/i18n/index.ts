import { ref } from 'vue'

type Locale = 'en' | 'zh-CN'

const currentLocale = ref<Locale>('en')

const messages: Record<Locale, Record<string, string>> = {
  en: {},
  'zh-CN': {},
}

export function setLocale(locale: Locale) {
  currentLocale.value = locale
}

export function getLocale(): Locale {
  return currentLocale.value
}

export function t(key: string): string {
  return messages[currentLocale.value]?.[key] || key
}

// 基础消息
const en = messages.en
en.hello = 'Hello'
en.login_title = 'Welcome to LAWA'
en.login_subtitle = 'Learn languages through real-world tasks'
en.login_button = 'Login'
en.register_title = 'Create Account'
en.register_subtitle = 'Start your language journey'
en.register_button = 'Register'
en.username = 'Username'
en.password = 'Password'
en.email = 'Email'
en.confirm_password = 'Confirm Password'
en.back_to_login = 'Back to Login'
en.loading = 'Loading...'
en.language_level = 'Language Level'
en.coins = 'Coins'
en.today_earned = 'Today Earned'
en.study_time = 'Study Time'
en.start_assessment = 'Assessment'
en.ai_companion = 'AI Companion'
en.learning_plan = 'Learning Plan'
en.today_tasks = "Today's Tasks"
en.tasks = 'Tasks'
en.publish_task = 'Publish Task'
en.all_status = 'All Status'
en.all_types = 'All Types'
en.no_tasks_yet = 'No tasks yet'
en.prev = 'Previous'
en.next = 'Next'
en.assessment = 'Assessment'
en.assessment_desc = 'Test your language skills'
en.select_language = 'Select Language'
en.start = 'Start'
en.balance = 'Balance'
en.today = 'Today'
en.week = 'This Week'
en.companion = 'AI Companion'
en.shop = 'Shop'
en.guild = 'Guild'
en.achievements = 'Achievements'
en.events = 'Events'
en.leaderboard = 'Leaderboard'
en.match = 'Match'
en.vocabulary = 'Vocabulary'
en.tutor = 'Tutor'
en.help = 'Help'
en.plan = 'Plan'
en.register = 'Register'
en.logout = 'Logout'
en.dashboard = 'Dashboard'
en.create_task = 'Create Task'
en.task_detail = 'Task Detail'
en.coin_history = 'Coin History'
en.reward = 'Reward'
en.spend = 'Spend'
en.status = 'Status'
en.pending = 'Pending'
en.completed = 'Completed'
en.difficulty = 'Difficulty'
en.reward_coin = 'Reward Coin'

