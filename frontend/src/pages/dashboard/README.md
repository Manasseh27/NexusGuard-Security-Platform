# Dashboard Refactoring

## Structure

This folder contains the refactored Dashboard component, split into modular, reusable pieces:

```
dashboard/
├── Dashboard.tsx              # Main orchestrator component
├── constants/
│   └── index.ts              # Framework metadata, severity levels, constants
├── hooks/
│   ├── useDashboardData.ts   # Custom hooks for data transformation
│   └── index.ts              # Hook exports
├── panels/
│   ├── KPICards.tsx          # Top-level KPI metrics
│   ├── ScoreRingPanel.tsx    # Overall compliance score
│   ├── ComplianceTrendPanel.tsx
│   ├── FrameworkRadarPanel.tsx
│   ├── ComplianceFrameworksPanel.tsx
│   ├── DriftEventsPanel.tsx  # Active drift detection
│   ├── SeverityDistributionPanel.tsx
│   ├── FleetStatusPanel.tsx
│   └── index.ts              # Panel exports
├── widgets/
│   ├── DashboardFooter.tsx   # Footer with service status
│   └── index.ts              # Widget exports
└── README.md                 # This file
```

## Key Improvements

- **Modularity**: Each panel is a separate, testable component
- **Reusability**: Hooks like `useSeverityCounts()`, `useRadarData()` are shareable
- **Maintainability**: Logic is separated by concern (data transform, UI rendering, constants)
- **Performance**: Components use `React.memo()` and `useMemo()` for optimization
- **Scalability**: Easy to add new panels or customize existing ones

## Component Hierarchy

```
Dashboard
├── TopNav
├── LiveTicker
├── KPICards
├── ScoreRingPanel
├── ComplianceTrendPanel
├── FrameworkRadarPanel
├── ComplianceFrameworksPanel
├── DriftEventsPanel
├── SeverityDistributionPanel
├── FleetStatusPanel
└── DashboardFooter
```

## Data Flow

1. **Data Fetching**: `useFleetPolling()` (from hooks) fetches fleet & drift data
2. **Transformations**: Custom hooks (`useSeverityCounts`, `useRadarData`) compute derived data
3. **Panel Rendering**: Each panel receives pre-computed data as props
4. **User Actions**: Callbacks (e.g., `onAcknowledge`) bubble up to store

## Adding a New Panel

1. Create `panels/NewPanel.tsx`
2. Define props interface
3. Render with styled components
4. Add to `panels/index.ts` exports
5. Import and render in `Dashboard.tsx`

## Testing

Each component can be tested in isolation:

```typescript
// Example: Test ScoreRingPanel
render(
  <ScoreRingPanel
    score={85}
    healthy={45}
    drifting={5}
    unreachable={0}
    total={50}
  />
);
```

## Performance Notes

- All hooks use `useMemo()` to prevent unnecessary re-renders
- Consider wrapping panels with `React.memo()` if they receive stable props
- LiveTicker limits to first 10 events to avoid rendering overhead
- Drift events panel shows only top 5 to reduce DOM nodes
