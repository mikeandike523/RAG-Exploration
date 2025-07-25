// Shared message types for the live progress viewer

export interface TitleStyle {
  backgroundColor?: string;
  color?: string;
  fontWeight?: 'bold' | 'normal';
  fontStyle?: 'italic' | 'normal';
  fontSize?: string;
}

export interface TextMessage {
  kind: 'string';
  text: string;
  backgroundColor?: string;
  color?: string;
  fontWeight?: 'bold' | 'normal';
  fontStyle?: 'italic' | 'normal';
  fontSize?: string;
  title?: string;
  titleStyle?: TitleStyle;
}

export interface ProgressBarMessage {
  kind: 'progressBar';
  title: string;
  unit?: string;
  precision?: number;
  showAsPercent: boolean;
  max: number;
  current: number;
  titleStyle?: TitleStyle;
}

export type ProgressMessage = TextMessage | ProgressBarMessage;
