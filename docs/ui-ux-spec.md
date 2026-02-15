# SMTG Frontend UI/UX Specification

## 1) Product UX Intent

- Role: calm productivity companion (not punitive blocker).
- Tone: supportive, non-judgmental, trust-first.
- Core behavior: detect patterns, suggest breaks, preserve autonomy.

## 2) Information Architecture

Bottom navigation (4 tabs):
1. Home
2. Insights
3. Focus
4. Settings

Additional flows:
- Onboarding (4 screens)
- Subscription screen

## 3) Visual Language

- Style: minimal + calm + premium + data-light.
- Avoid aggressive warning patterns and heavy gamification.
- 8px spacing grid and rounded cards.

## 4) Screen Behavior

### Onboarding
- 4-step trust-first setup with goal selection.

### Home
- Greeting + focus score pill.
- Circular progress ring for used-vs-goal minutes.
- AI insight and streak summary.

### Insights
- Weekly bar chart.
- Time-saved line chart.
- Behavior analysis card (risk + recommendations).

### Focus
- Full-screen timer with calm message.

### Settings
- Profile fields.
- Mode toggles.
- Theme selection.
- Integration compatibility list.
- Data export / activity deletion.

### Subscription
- Free/Pro status and upgrade/downgrade controls.

## 5) Components

- Buttons: Primary / Secondary / Ghost.
- Cards: Summary / Settings / Insights.
- Progress ring.
- Chart blocks.
- Nudge bottom sheet.
- Integration status rows.

## 6) Motion

- Transitions: 200–300ms fade/slide.
- Bottom sheet: spring-like slide up.
- Ring: smooth sweep update.

## 7) Trust & Privacy UX

- Explain detection boundaries (not content scanning).
- Export data JSON.
- Delete activity data.
- Integration messaging reflects policy-safe limitations.
