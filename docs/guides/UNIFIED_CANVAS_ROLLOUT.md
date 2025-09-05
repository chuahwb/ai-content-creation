# Unified Creative Canvas Rollout Guide

This guide covers the rollout of the new Unified Creative Canvas feature that replaces the traditional mode-based interface with a progressive, lens-based approach.

## Feature Overview

The Unified Creative Canvas introduces:

- **Single entry point**: Replace three separate modes with one unified interface
- **Progressive disclosure**: Advanced features revealed through "lenses" (Brand, Text, Marketing)
- **Template gallery**: Visual template selection instead of task-specific mode
- **Unified brief**: Single creative input that replaces prompt/imageInstruction/taskDescription
- **Content-driven validation**: No longer depends on mode selection

## Feature Flags

### Frontend Flags

- **`NEXT_PUBLIC_UNIFIED_CANVAS`**: Controls the new Creative Canvas UI
  - `true`: Show new unified interface
  - `false`: Show legacy mode-based interface
  - Default: `true` in development

### Backend Flags

- **`ENABLE_UNIFIED_BRIEF`**: Controls unified brief processing
  - `true`: Process unified_brief field and normalize into context
  - `false`: Ignore unified_brief, use legacy fields only
  - Default: `true`

## Rollout Strategy

### Phase 1: Development Testing
```bash
# Enable in development environment
NEXT_PUBLIC_UNIFIED_CANVAS=true
ENABLE_UNIFIED_BRIEF=true
```

### Phase 2: Staging Validation
```bash
# Test both interfaces in staging
NEXT_PUBLIC_UNIFIED_CANVAS=true  # New interface
ENABLE_UNIFIED_BRIEF=true        # Backend support
```

### Phase 3: Production Rollout

#### Option A: Feature Toggle (Recommended)
```bash
# Start with legacy interface, enable for specific users/sessions
NEXT_PUBLIC_UNIFIED_CANVAS=false  # Default to legacy
ENABLE_UNIFIED_BRIEF=true         # Backend supports both
```

#### Option B: Full Rollout
```bash
# Enable for all users
NEXT_PUBLIC_UNIFIED_CANVAS=true
ENABLE_UNIFIED_BRIEF=true
```

### Phase 4: Legacy Cleanup (Future)
After successful rollout and user feedback:
- Remove `NEXT_PUBLIC_UNIFIED_CANVAS` flag
- Remove legacy mode-based UI code
- Remove mode field from API (optional, can keep for analytics)

## Compatibility Matrix

| Frontend Canvas | Backend Brief | Result |
|----------------|---------------|---------|
| Legacy (false) | Enabled (true) | Legacy UI + Backend accepts both formats |
| Unified (true) | Enabled (true) | New UI + Full unified brief processing |
| Legacy (false) | Disabled (false) | Legacy UI + Legacy processing only |
| Unified (true) | Disabled (false) | New UI + Legacy field mapping only |

## Monitoring and Rollback

### Key Metrics to Monitor
- Form submission success rate
- Pipeline run completion rate
- User engagement with new features (lens usage, template selection)
- Error rates in unified brief processing

### Quick Rollback
If issues are detected, immediately revert flags:
```bash
# Emergency rollback to legacy interface
NEXT_PUBLIC_UNIFIED_CANVAS=false
# Keep backend support enabled for compatibility
ENABLE_UNIFIED_BRIEF=true
```

### Gradual Rollback
For partial issues, selectively disable features:
- Keep unified canvas but disable specific lenses
- Enable unified canvas for specific user segments
- A/B test between interfaces

## Testing Checklist

### Pre-Rollout Testing
- [ ] All existing functionality works in legacy mode
- [ ] All existing functionality works in unified mode
- [ ] Form validation works correctly in both modes
- [ ] Backend processes both legacy and unified formats
- [ ] WebSocket updates work correctly
- [ ] Brand kit functionality preserved
- [ ] Preset loading/saving works
- [ ] Image upload and editing works

### Post-Rollout Monitoring
- [ ] Monitor error rates in logs
- [ ] Check pipeline completion rates
- [ ] Verify user engagement metrics
- [ ] Monitor support tickets for UI confusion
- [ ] Track feature adoption (lens usage, template selection)

## User Communication

### Internal Team
- Notify developers of flag changes
- Update deployment documentation
- Share rollout timeline with stakeholders

### External Users (if applicable)
- Feature announcement highlighting benefits
- Optional tutorial or tour for new interface
- Support documentation updates
- Feedback collection mechanism

## Configuration Examples

### Development
```env
# Full new experience for development
NEXT_PUBLIC_UNIFIED_CANVAS=true
ENABLE_UNIFIED_BRIEF=true
```

### Staging
```env
# Test both interfaces
NEXT_PUBLIC_UNIFIED_CANVAS=true
ENABLE_UNIFIED_BRIEF=true
```

### Production (Conservative)
```env
# Start conservative, expand gradually
NEXT_PUBLIC_UNIFIED_CANVAS=false
ENABLE_UNIFIED_BRIEF=true
```

### Production (Aggressive)
```env
# Full rollout for confident deployment
NEXT_PUBLIC_UNIFIED_CANVAS=true
ENABLE_UNIFIED_BRIEF=true
```

## Troubleshooting

### Common Issues

**Issue**: Form submission fails with unified canvas
- **Check**: Backend ENABLE_UNIFIED_BRIEF flag
- **Fix**: Ensure backend can process unified_brief JSON

**Issue**: Legacy features missing in unified canvas
- **Check**: Lens components properly implemented
- **Fix**: Verify all legacy features mapped to appropriate lenses

**Issue**: Validation errors with new interface
- **Check**: Content-driven validation logic
- **Fix**: Ensure validation doesn't depend on deprecated mode field

**Issue**: WebSocket connection issues
- **Check**: Navigation timing in form submission
- **Fix**: Verify navigate-first pattern preserved

### Debug Commands

```bash
# Check current flag values
echo $NEXT_PUBLIC_UNIFIED_CANVAS
echo $ENABLE_UNIFIED_BRIEF

# Test API with unified brief
curl -X POST /api/v1/runs \
  -F "platform_name=Instagram Post (1:1 Square)" \
  -F "unified_brief={\"intentType\":\"fullGeneration\",\"generalBrief\":\"test\"}"

# Monitor logs for unified brief processing
tail -f logs/churns.log | grep "unified_brief"
```

## Success Criteria

The rollout is considered successful when:
- [ ] Form submission success rate >= baseline
- [ ] Pipeline completion rate >= baseline
- [ ] User engagement metrics stable or improved
- [ ] Error rates within acceptable thresholds
- [ ] Support ticket volume unchanged
- [ ] User feedback positive or neutral

## Next Steps

After successful rollout:
1. Collect user feedback on new interface
2. Analyze usage patterns for lens adoption
3. Consider removing legacy code (Phase 4)
4. Plan additional UX improvements based on data
5. Document lessons learned for future feature rollouts
