export type ContentType =
  | 'text'
  | 'diagram'
  | 'flipCard'
  | 'mindmap'
  | 'audio'
  | 'quiz'
  | 'miniGame';

export interface ContentUpdate {
  id: string;
  type: ContentType;
  data: any;
}
