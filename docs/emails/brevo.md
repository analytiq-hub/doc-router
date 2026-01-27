Here’s the **clean, authoritative list of attributes you can use inside HTML emails sent by Brevo**, plus how they differ by email type. This is the stuff that actually works in production.

---

## 🧩 1. Contact attributes (most common)

These come from **Contacts → Attributes** in Brevo and are usable in **campaigns & automations**.

### Syntax

```html
{{ contact.ATTRIBUTE_NAME }}
```

### Default built-in contact attributes

These exist in every Brevo account:

```text
EMAIL
FIRSTNAME
LASTNAME
SMS
WHATSAPP
COMPANY
ADDRESS
CITY
ZIP_CODE
COUNTRY
STATE
```

Example:

```html
Hi {{ contact.FIRSTNAME }},
```

### Custom contact attributes

Any attribute you create (text, number, date, boolean, etc.):

```html
{{ contact.plan }}
{{ contact.signup_date }}
{{ contact.company_size }}
```

⚠️ Attribute names are **case-sensitive** and must match exactly.

---

## 🧠 2. Fallback values (very important)

To avoid blank output when data is missing:

```html
{{ contact.FIRSTNAME | default: 'there' }}
```

Example:

```html
Hi {{ contact.FIRSTNAME | default: 'friend' }},
```

---

## ✉️ 3. System & compliance attributes

These are **mandatory / auto-managed** by Brevo.

### Unsubscribe

```html
{{ unsubscribe }}
```

Example:

```html
<a href="{{ unsubscribe }}">Unsubscribe</a>
```

### Manage preferences

```html
{{ update_profile }}
```

### Mirror (view in browser)

```html
{{ mirror }}
```

---

## 🧾 4. Campaign & sender metadata

Useful for branding or legal copy:

```html
{{ sender.name }}
{{ sender.email }}
{{ sender.company }}
{{ sender.address }}
```

Example:

```html
Sent by {{ sender.company }} · {{ sender.address }}
```

---

## ⚙️ 5. Transactional email attributes (SMTP / API)

These are **not contact attributes** — they are passed dynamically when you send the email via API, SMTP, or workflow trigger.

### Syntax

```html
{{ params.variable_name }}
```

### Example API payload

```json
{
  "to": [{ "email": "user@example.com" }],
  "params": {
    "first_name": "Andrei",
    "plan": "Pro",
    "reset_link": "https://example.com/reset"
  }
}
```

### HTML usage

```html
Hi {{ params.first_name }},
Your plan: {{ params.plan }}
<a href="{{ params.reset_link }}">Reset password</a>
```

---

## 🔁 6. Event & automation attributes

Used in **Automation workflows**, triggered by events:

```html
{{ event.name }}
{{ event.date }}
{{ event.amount }}
```

These depend entirely on the event schema you defined.

---

## 🧮 7. Conditional logic (advanced but supported)

Brevo supports **basic logic filters**:

```html
{% if contact.plan == 'enterprise' %}
  <p>Thanks for being an Enterprise customer!</p>
{% endif %}
```

Fallback example:

```html
{% if contact.FIRSTNAME %}
  Hi {{ contact.FIRSTNAME }},
{% else %}
  Hi there,
{% endif %}
```

---

## 🚫 Things that are NOT supported

Good to know upfront:

❌ JavaScript
❌ Complex loops (`for` loops are limited)
❌ Arbitrary object traversal
❌ Fetching external data

Emails must remain **deterministic and static at send time**.

---

## ✅ Practical cheat sheet

| Use case        | Syntax                                        |
| --------------- | --------------------------------------------- |
| First name      | `{{ contact.FIRSTNAME }}`                     |
| Safe first name | `{{ contact.FIRSTNAME \| default: 'there' }}` |
| Custom field    | `{{ contact.my_field }}`                      |
| API param       | `{{ params.order_id }}`                       |
| Unsubscribe     | `{{ unsubscribe }}`                           |
| Preferences     | `{{ update_profile }}`                        |
| Sender name     | `{{ sender.name }}`                           |

---

## 🔍 Where to see your exact attributes in Brevo

1. Go to **Contacts → Attributes**
2. Click **Edit**
3. Use the **ATTRIBUTE NAME** column (not the label)

That exact string is what you use in HTML.