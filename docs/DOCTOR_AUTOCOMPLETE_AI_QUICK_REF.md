# Doctor Autocomplete - AI Agent Quick Reference

## 🚨 ПЕРЕД НАЧАЛОМ РАБОТЫ

**ОБЯЗАТЕЛЬНО ПРОЧИТАЙТЕ:** `DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md`

---

## ⚡ Quick Rules (TL;DR)

```
DO:
✅ Search in doctor's history
✅ Rank by frequency
✅ WHERE doctor_id = current_user_id
✅ Check readiness before showing

DON'T:
❌ Generate text with AI/LLM
❌ Share data between doctors
❌ Modify doctor's original text
❌ Cache medical content on frontend
❌ Add "smart" features without approval
```

---

## 📁 Files You Can Safely Modify

### ✅ SAFE (UI/Performance):
- `frontend/src/components/emr/EMRSmartField.css` - Styling
- Database indexes (add, not remove)
- Telemetry dashboard queries
- Error handling logic

### ⚠️ REQUIRES REVIEW (Logic):
- `backend/app/services/doctor_phrase_service.py` - Search logic
- `backend/app/services/emr_phrase_indexer.py` - Indexing logic
- `frontend/src/hooks/useDoctorPhrases.js` - Hook logic

### 🔴 CRITICAL (Don't Touch Without Approval):
- `backend/app/services/doctor_autocomplete_readiness.py` - Readiness criteria
- `INDEXABLE_FIELDS` list - Medical field selection
- `MIN_COMPLETED_EMRS`, `MIN_STORED_PHRASES` constants

---

## 🔍 Code Smell Checklist

### 🚩 RED FLAGS:
```python
# If you see ANY of these, STOP:

import openai                    # AI generation - FORBIDDEN
import anthropic                 # LLM - FORBIDDEN
from transformers import ...     # ML models - FORBIDDEN

.replace("ГБ", "...")           # Text modification - FORBIDDEN
spell_check(phrase)              # Autocorrect - FORBIDDEN
nlp.improve(text)                # Text enhancement - FORBIDDEN

SELECT * FROM ... WHERE true     # Missing doctor_id filter - DANGEROUS
localStorage.setItem(phrases)    # Caching meddata - DANGEROUS
```

### ✅ GREEN FLAGS:
```python
# These are GOOD:

WHERE doctor_id = :current_doctor_id    # Isolation
.strip()                                # Minimal cleanup
ORDER BY usage_count DESC               # Frequency ranking
if not ready: return []                 # Readiness check
```

---

## 🧪 Testing Checklist

Before committing ANY change, test:

```bash
# 1. Isolation test
curl -H "Authorization: Bearer doctor_A_token" \
  http://localhost:8000/api/v1/emr/phrase-suggest \
  -d '{"doctorId": B, ...}'
# Expected: 403 Forbidden or empty results

# 2. Readiness test
curl http://localhost:8000/api/v1/emr/readiness/123
# Expected: ready=false if < 10 EMRs

# 3. SQL injection test
curl -d '{"currentText": "'; DROP TABLE doctor_phrase_history; --"}'
# Expected: No error, safe escape

# 4. XSS test
curl -d '{"currentText": "<script>alert(1)</script>"}'
# Expected: Text escaped in response
```

---

## 🐛 Common Mistakes

### Mistake #1: Forgetting `doctor_id` filter
```python
# ❌ WRONG
phrases = db.query(DoctorPhraseHistory).filter(
    DoctorPhraseHistory.field == field
).all()

# ✅ RIGHT
phrases = db.query(DoctorPhraseHistory).filter(
    DoctorPhraseHistory.doctor_id == current_user_id,  # ← ADD THIS!
    DoctorPhraseHistory.field == field
).all()
```

### Mistake #2: Caching medical data
```javascript
// ❌ WRONG
localStorage.setItem('suggestions', JSON.stringify(phrases));

// ✅ RIGHT
// Don't cache suggestions at all, or use in-memory with TTL
const cache = new Map(); // In-memory, session-scoped
```

### Mistake #3: String concatenation in SQL
```python
# ❌ WRONG (SQL Injection!)
query = f"SELECT * FROM ... WHERE prefix_3 = '{prefix}'"

# ✅ RIGHT (ORM auto-escapes)
.filter(DoctorPhraseHistory.prefix_3 == prefix[:3])
```

---

## 📞 When to Ask for Help

Ask IMMEDIATELY if you want to:
- Change readiness criteria
- Add new INDEXABLE_FIELDS
- Modify ranking algorithm
- Add any AI/ML features
- Share data between doctors
- Cache medical content
- Change telemetry collection

**Default answer is NO. You need strong justification.**

---

## 🎯 Philosophy Reminders

```
"We help doctors REMEMBER what they wrote,
 not try to be smarter than them."

Core Principles:
1. Search, not Generate
2. Privacy First
3. Transparency Always
4. Simple > Complex
5. Medical Safety > User Convenience
```

---

## 🔗 Documentation Links

- **[LAWS FOR AI](./DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md)** ← READ FIRST!
- [API Reference](./DOCTOR_AUTOCOMPLETE_API.md)
- [Deployment Guide](./DOCTOR_AUTOCOMPLETE_DEPLOYMENT.md)
- [UX Guide](./EMR_SMART_AUTOCOMPLETE_UX.md)

---

*Keep this reference open while working on Doctor Autocomplete!*
