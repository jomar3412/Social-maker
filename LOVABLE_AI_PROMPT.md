# Lovable AI - Content Pipeline Dashboard Builder Prompt

## Overview

Build a web-based dashboard application for a **Short-Form Social Media Content Generation Pipeline**. This system generates viral content (hooks, scripts, captions, hashtags, visual direction, voice direction) for platforms like TikTok, YouTube Shorts, and Instagram Reels.

The critical feature is a **Structured Clarification Gate** that ensures all required inputs are confirmed before any content generation begins.

---

## Core Architecture Requirements

### Tech Stack (Recommended)
- **Frontend**: React + TypeScript + Tailwind CSS
- **State Management**: Zustand or React Context
- **UI Components**: shadcn/ui or Radix UI primitives
- **Backend**: Node.js/Express or Supabase Edge Functions
- **Database**: Supabase (PostgreSQL) or Firebase
- **Authentication**: Supabase Auth or Clerk

### Design Philosophy
- Mobile-first responsive design
- Dark mode as default with light mode toggle
- Smooth animations and transitions
- Clear visual hierarchy
- Accessibility compliant (WCAG 2.1 AA)

---

## Feature 1: Clarification Gate System

### 1.1 Mandatory Niche Selection

When a user initiates content creation, the system MUST first display:

```
"What niche would you like to create content for?"
```

**Required Options (as selectable cards):**

| Option | Label | Description |
|--------|-------|-------------|
| motivation | Motivation | Inspirational content for daily motivation |
| facts | Facts | Did you know? Fun facts and trivia |
| finance | Finance | Money, investing, and financial wisdom |
| fitness | Fitness | Workout motivation and health tips |
| random | Random | Let the system choose - skip niche questions |
| custom | Custom | Define your own niche |

**UI Behavior:**
- Display as large, clickable cards with icons
- Highlight selected option
- "Random" option should have visual indicator that it skips follow-up questions
- "Custom" option should expand an input field for custom niche name

**Conditional Logic:**
- If user selects "Random" → Skip to Final Clarification
- If user selects any other niche → Trigger niche-specific questions

---

### 1.2 Motivation Niche Questions

If `niche === "motivation"`, display the following questions in sequence:

#### Question 1: Time Slot

```
"What time slot are you targeting?"
```

| Value | Label | Description |
|-------|-------|-------------|
| morning | Morning (8-9 AM) | Start the day strong |
| midday | Midday (11 AM-12 PM) | Midday motivation boost |
| after_work | After Work (5-6 PM) | Post-work wind down |
| night | Night (9-10 PM) | Reflective evening content |
| auto | Auto-select | System calculates optimal slot |

**Auto-select Logic:**
When "Auto" is selected, the system must:
1. Get current time from user's timezone
2. Calculate next available posting window
3. Display calculated recommendation:
   ```
   "Recommended: Morning (8-9 AM) - 2024-01-15 08:00"
   ```
4. Allow user to confirm or override

#### Question 2: Tone

```
"What tone should the content have?"
```

| Value | Label | Description |
|-------|-------|-------------|
| generic_affirmation | Generic Affirmation | Warm, supportive, universal |
| aggressive_gym | Aggressive / Gym Energy | High energy, intense, push hard |
| calm_reflective | Calm Reflective | Peaceful, thoughtful, introspective |
| spiritual | Spiritual | Soul-focused, deeper meaning |
| business_focused | Business-Focused | Success, hustle, entrepreneurship |

#### Question 3: Quote Type

```
"What type of quote/message?"
```

| Value | Label | Description |
|-------|-------|-------------|
| original | Original Quote | AI-generated original message |
| real_person | Real Person Quote | Quote from a known figure |
| mix | Mix | Combination of both styles |

**Note:** If "real_person" or "mix" is selected, optionally display:
```
"Any specific person or era to draw from? (optional)"
```

#### Question 4: Voiceover Style

```
"What voiceover style?"
```

| Value | Label | Description |
|-------|-------|-------------|
| neutral_ai | Neutral AI | Clean, professional AI voice |
| deep_motivational | Deep Motivational | Rich, inspiring voice |
| energetic | Energetic | Fast-paced, high energy |
| text_only | Text Only | No voiceover, just text on screen |

---

### 1.3 Other Niche Question Sets

**IMPORTANT:** The system should be designed to easily add question sets for other niches. Use a configuration-driven approach:

```typescript
interface NicheQuestionSet {
  niche: string;
  questions: Question[];
}

interface Question {
  id: string;
  question: string;
  type: 'single_choice' | 'multi_choice' | 'text' | 'number';
  options?: Option[];
  required: boolean;
  conditional?: {
    dependsOn: string;
    values: string[];
  };
}
```

**Facts Niche (basic):**
- Category: science, history, nature, space, human body, technology
- Voiceover Style: (same as motivation)

**Finance Niche (basic):**
- Topic: investing, saving, crypto, budgeting, debt, taxes
- Audience Level: beginner, intermediate, advanced
- Voiceover Style: (same as motivation)

**Fitness Niche (basic):**
- Focus: motivation, workout tips, nutrition, recovery
- Intensity Level: beginner, intermediate, advanced
- Voiceover Style: (same as motivation)

**Custom Niche:**
- Custom niche name (text input)
- Custom instructions (text area)
- Voiceover Style: (same as motivation)

---

### 1.4 Universal Final Clarification

Before generation, the system MUST display:

```
"If you have any additional constraints, tone preferences,
or niche-specific instructions, please specify them now
before generation."
```

**UI Elements:**
- Large text area for optional input
- Character counter
- "Skip" or "Proceed without additional input" button
- "Generate Content" primary action button

**Generation Gate:**
- The "Generate Content" button must be disabled until:
  1. Niche is selected
  2. All required niche-specific questions are answered
  3. Final clarification step is reached (even if skipped)

---

## Feature 2: Structured Output Display

### 2.1 Output Sections

All generated content MUST be displayed in clearly labeled, separated sections:

```
┌─────────────────────────────────────────────────┐
│ GENERATED CONTENT                               │
├─────────────────────────────────────────────────┤
│                                                 │
│ ▼ HOOK                                          │
│ ┌─────────────────────────────────────────────┐ │
│ │ "You did good today. Really good."          │ │
│ └─────────────────────────────────────────────┘ │
│                                     [Copy] [Edit]│
│                                                 │
│ ▼ FULL SCRIPT                                   │
│ ┌─────────────────────────────────────────────┐ │
│ │ You did good today. Really good. You might  │ │
│ │ not see it. You might think it was just     │ │
│ │ another day. But it wasn't...               │ │
│ └─────────────────────────────────────────────┘ │
│                           [Copy] [Edit] [Expand]│
│                                                 │
│ ▼ CAPTION                                       │
│ ┌─────────────────────────────────────────────┐ │
│ │ You needed to hear this today.              │ │
│ └─────────────────────────────────────────────┘ │
│                                     [Copy] [Edit]│
│                                                 │
│ ▼ HASHTAGS                                      │
│ ┌─────────────────────────────────────────────┐ │
│ │ #motivation #youvegotthis #dailyreminder    │ │
│ │ #selfcare #youreenough                      │ │
│ └─────────────────────────────────────────────┘ │
│                           [Copy] [Edit] [Suggest]│
│                                                 │
│ ▼ VISUAL DIRECTION                              │
│ ┌─────────────────────────────────────────────┐ │
│ │ Warm, soft visuals. Sunrise/sunset shots.   │ │
│ │ Person walking alone on beach or mountain.  │ │
│ │ Soft color grading (warm tones). Slow pans. │ │
│ └─────────────────────────────────────────────┘ │
│                                     [Copy] [Edit]│
│                                                 │
│ ▼ VOICE DIRECTION                               │
│ ┌─────────────────────────────────────────────┐ │
│ │ Calm, low, warm - firm but not a whisper.   │ │
│ │ Supportive and encouraging undertone.       │ │
│ └─────────────────────────────────────────────┘ │
│                                     [Copy] [Edit]│
│                                                 │
│ ▼ POSTING TIME RECOMMENDATION                   │
│ ┌─────────────────────────────────────────────┐ │
│ │ Recommended: Morning (8-9 AM)               │ │
│ │ Best day: Tuesday or Thursday               │ │
│ │ Suggested: 2024-01-16 08:30 AM              │ │
│ └─────────────────────────────────────────────┘ │
│                              [Schedule] [Override]│
│                                                 │
├─────────────────────────────────────────────────┤
│ [Regenerate Section ▼]  [Export All]  [Save]    │
│ [Generate Video]  [Schedule Post]               │
└─────────────────────────────────────────────────┘
```

### 2.2 Section Actions

Each section should support:

| Action | Behavior |
|--------|----------|
| Copy | Copy section content to clipboard with toast notification |
| Edit | Inline editing with save/cancel |
| Expand | Show full content in modal (for long scripts) |
| Suggest | AI suggestions for improvement (hashtags) |
| Regenerate | Regenerate only this section |

### 2.3 Export Options

- **Copy All**: Copy all sections as formatted text
- **Export JSON**: Download as JSON file
- **Export Markdown**: Download as formatted markdown
- **Send to Editor**: Open in video editor integration (if available)

---

## Feature 3: Generation Flow State Machine

### 3.1 Flow States

```typescript
type FlowState =
  | 'idle'
  | 'niche_selection'
  | 'niche_questions'
  | 'final_clarification'
  | 'ready_for_generation'
  | 'generating'
  | 'completed'
  | 'error';
```

### 3.2 State Transitions

```
idle → niche_selection (user clicks "Create Content")
niche_selection → niche_questions (niche selected, except "random")
niche_selection → final_clarification (random selected)
niche_questions → final_clarification (all questions answered)
final_clarification → ready_for_generation (clarification submitted/skipped)
ready_for_generation → generating (user clicks "Generate")
generating → completed (generation successful)
generating → error (generation failed)
completed → niche_selection (user clicks "Create New")
error → niche_selection (user clicks "Try Again")
```

### 3.3 Progress Indicator

Display a step indicator showing:
```
[1. Niche] → [2. Details] → [3. Clarify] → [4. Generate]
    ✓           ●            ○              ○
```

---

## Feature 4: Dashboard Layout

### 4.1 Main Navigation

```
┌──────────────────────────────────────────────────────────┐
│ [Logo] SoCal Maker                    [User] [Settings]  │
├───────┬──────────────────────────────────────────────────┤
│       │                                                  │
│  📝   │   MAIN CONTENT AREA                             │
│Create │                                                  │
│       │                                                  │
│  📚   │                                                  │
│Library│                                                  │
│       │                                                  │
│  📅   │                                                  │
│Schedule│                                                 │
│       │                                                  │
│  📊   │                                                  │
│Analytics│                                                │
│       │                                                  │
│  ⚙️   │                                                  │
│Settings│                                                 │
│       │                                                  │
└───────┴──────────────────────────────────────────────────┘
```

### 4.2 Pages

| Page | Purpose |
|------|---------|
| Create | Main content creation with clarification gate |
| Library | Browse/search/filter past generated content |
| Schedule | Calendar view of scheduled posts |
| Analytics | Performance metrics (placeholder/future) |
| Settings | API keys, preferences, niche configs |

---

## Feature 5: Content Library

### 5.1 List View

```
┌─────────────────────────────────────────────────────────┐
│ Content Library                        [+ Create New]   │
├─────────────────────────────────────────────────────────┤
│ Filter: [All Niches ▼] [All Status ▼] [Search...]      │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🎯 "You did good today..."                          │ │
│ │ Motivation • Affirming • Jan 15, 2024              │ │
│ │ Status: Draft        [Edit] [Schedule] [Delete]    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🧪 "Octopuses have 3 hearts..."                     │ │
│ │ Facts • Nature • Jan 14, 2024                      │ │
│ │ Status: Posted (YT, TikTok)  [View] [Repost]       │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Content Status

| Status | Meaning |
|--------|---------|
| Draft | Generated but not posted |
| Scheduled | Scheduled for future posting |
| Posted | Successfully posted to platforms |
| Failed | Posting failed (with retry option) |

---

## Feature 6: Settings & Configuration

### 6.1 Niche Configuration

Allow users to:
- Add custom niches
- Modify question sets for each niche
- Set default values for frequently used options
- Create presets (e.g., "Morning Motivation Aggressive")

### 6.2 API Configuration

Store securely:
- OpenAI/Anthropic API keys (for AI generation)
- ElevenLabs API key (for voice generation)
- Social platform API credentials
- Webhook URLs

### 6.3 Preferences

- Default niche
- Default time slot
- Timezone
- Theme (dark/light/system)
- Notification preferences

---

## Feature 7: API Endpoints (Backend)

### 7.1 Required Endpoints

```
POST /api/content/generate
  Body: { niche, nicheConfig, additionalConstraints }
  Response: { hook, fullScript, caption, hashtags, visualDirection, voiceDirection, postingTime }

GET /api/content
  Query: { niche?, status?, search?, page?, limit? }
  Response: { items: Content[], total, page, pages }

GET /api/content/:id
  Response: Content

PUT /api/content/:id
  Body: Partial<Content>
  Response: Content

DELETE /api/content/:id
  Response: { success: true }

POST /api/content/:id/schedule
  Body: { platforms: string[], scheduledTime: string }
  Response: { scheduledId, platforms, time }

GET /api/niches
  Response: { niches: NicheConfig[] }

POST /api/niches
  Body: NicheConfig
  Response: NicheConfig

GET /api/niches/:niche/questions
  Response: { questions: Question[] }
```

### 7.2 Data Models

```typescript
interface Content {
  id: string;
  niche: string;
  nicheConfig: Record<string, any>;
  hook: string;
  fullScript: string;
  caption: string;
  hashtags: string[];
  visualDirection: string;
  voiceDirection: string;
  postingTimeRecommendation: string;
  status: 'draft' | 'scheduled' | 'posted' | 'failed';
  platforms: string[];
  createdAt: string;
  updatedAt: string;
  postedAt?: string;
  scheduledFor?: string;
}

interface NicheConfig {
  niche: string;
  displayName: string;
  description: string;
  icon: string;
  questions: Question[];
  defaults?: Record<string, any>;
}

interface Question {
  id: string;
  question: string;
  type: 'single_choice' | 'multi_choice' | 'text' | 'number';
  options?: Array<{
    value: string;
    label: string;
    description?: string;
  }>;
  required: boolean;
  default?: any;
}
```

---

## Feature 8: Responsive Design Requirements

### 8.1 Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile | < 640px | Single column, bottom nav, collapsible sections |
| Tablet | 640-1024px | Two columns, side nav |
| Desktop | > 1024px | Full layout with side nav |

### 8.2 Mobile-Specific

- Bottom navigation bar
- Full-screen modals for creation flow
- Swipe gestures for navigation
- Touch-friendly button sizes (min 44px)

---

## Implementation Notes for Lovable AI

### What to Infer

Since you don't have full visibility into the existing backend implementation:

1. **AI Generation**: Infer that generation calls an external AI API (OpenAI/Anthropic). Design the frontend to be API-agnostic.

2. **Voice Generation**: Assume ElevenLabs or similar. Include loading states for potentially long generation times.

3. **Video Generation**: This is handled by a separate pipeline. The dashboard should support "Send to Video Pipeline" action that triggers external processing.

4. **Platform Posting**: Assume OAuth-based connections to TikTok, YouTube, Instagram. Include placeholder connection UI.

### Scalability Considerations

1. **Adding New Niches**: The question system should be fully configuration-driven. Adding a new niche should only require adding to a config file or database.

2. **New Question Types**: Support for new question types (sliders, date pickers, file uploads) should be possible without major refactoring.

3. **Multi-Language**: Structure text to support i18n from the start.

4. **Multi-Tenant**: Consider user isolation if this becomes a SaaS product.

### Error Handling

1. Display clear error messages
2. Show retry options for failed operations
3. Save draft state to prevent data loss
4. Graceful degradation when API is unavailable

---

## Quick Start Commands

After generating the scaffold:

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local

# Run development server
npm run dev

# Build for production
npm run build
```

---

## Success Criteria

The dashboard is complete when:

1. [ ] User can select a niche before any generation
2. [ ] Motivation niche triggers all 4 required questions
3. [ ] Random niche skips to final clarification
4. [ ] Generation is blocked until clarification is complete
5. [ ] Final clarification prompt is always shown
6. [ ] Output displays all 7 required sections clearly labeled
7. [ ] Each section has copy/edit functionality
8. [ ] Content can be saved to library
9. [ ] Content can be scheduled for posting
10. [ ] Settings page allows API key configuration

---

## Files to Generate

1. `src/components/ClarificationGate/` - Main clarification flow
2. `src/components/NicheSelector/` - Niche selection cards
3. `src/components/QuestionFlow/` - Dynamic question renderer
4. `src/components/StructuredOutput/` - Output display sections
5. `src/components/ContentLibrary/` - Content list and filters
6. `src/pages/Create.tsx` - Main creation page
7. `src/pages/Library.tsx` - Content library page
8. `src/pages/Schedule.tsx` - Scheduling calendar
9. `src/pages/Settings.tsx` - Configuration page
10. `src/hooks/useClarificationFlow.ts` - State machine hook
11. `src/api/content.ts` - API client
12. `src/types/index.ts` - TypeScript definitions
13. `src/config/niches.ts` - Niche configurations

---

**END OF LOVABLE AI PROMPT**
