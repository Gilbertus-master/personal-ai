export interface CalendarEvent {
  id: string;
  subject: string;
  start: string;
  end: string;
  organizer?: string;
  attendees?: string[];
  location?: string;
  is_online?: boolean;
}

export interface CalendarConflict {
  event_a: CalendarEvent;
  event_b: CalendarEvent;
  overlap_minutes: number;
}

export interface CalendarAnalytics {
  total_meetings: number;
  total_hours: number;
  meetings_by_day: Record<string, number>;
  focus_time_hours: number;
  meeting_categories?: Record<string, number>;
}

export interface CalendarSuggestion {
  subject: string;
  suggested_attendees: string[];
  reason: string;
  priority?: string;
}

export interface MeetingPrep {
  meeting: CalendarEvent;
  brief: string;
  participants_info: {
    name: string;
    role?: string;
    recent_topics?: string[];
  }[];
  recent_context: string[];
}

export interface MeetingMinutes {
  id: number;
  document_id: number;
  title: string;
  date: string | null;
  participants: string | null;
  summary: string;
  created: string;
}

export interface MeetingROI {
  meetings: {
    subject: string;
    roi_score: number;
    reason: string;
  }[];
  summary: string;
}

export interface DeepWorkRequest {
  date?: string;
  start_hour?: number;
  end_hour?: number;
}

export interface DeepWorkResponse {
  success: boolean;
  message: string;
}

export interface CalendarEventsResponse {
  events: CalendarEvent[];
}

export interface CalendarConflictsResponse {
  conflicts: CalendarConflict[];
}

export interface MeetingSuggestionsResponse {
  suggestions: CalendarSuggestion[];
}
