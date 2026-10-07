import os
import resend
from datetime import datetime, date
from database import get_db_connection

resend.api_key = os.getenv("RESEND_API_KEY")

THRESHOLDS = {
    90: "notified_90",
    30: "notified_30",
    7:  "notified_7",
    1:  "notified_1"
}

def check_and_dispatch_expiries():
    """
    Runs daily via APScheduler:
    1. Evaluates all active documents across all users.
    2. Identifies crossed notification thresholds.
    3. Bundles up to 100 emails per batch request to maximize throughput.
    4. Atomically updates notification flags in SQLite.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all active documents with their owner's email
    cursor.execute("""
        SELECT d.id, d.document_type, d.expiry_date, d.notified_90, 
               d.notified_30, d.notified_7, d.notified_1, u.email
        FROM documents d
        JOIN users u ON d.user_id = u.id
        WHERE d.status = 'ACTIVE'
    """)
    records = cursor.fetchall()
    
    today = date.today()
    batch_payload = []
    updates_to_commit = [] # list of (column_name, doc_id)

    for row in records:
        try:
            exp_date = datetime.strptime(row["expiry_date"], "%Y-%m-%d").date()
        except ValueError:
            continue
            
        days_remaining = (exp_date - today).days
        
        # Check thresholds from highest to lowest
        for threshold, column_flag in THRESHOLDS.items():
            if days_remaining <= threshold and not row[column_flag]:
                subject_urgency = "URGENT ACTION" if threshold <= 7 else "Reminder"
                batch_payload.append({
                    "from": "ExpiryWatch <onboarding@resend.dev>",
                    "to": [row["email"]],
                    "subject": f"[{subject_urgency}] {row['document_type']} expires in {days_remaining} days",
                    "html": f"""
                        <div style="font-family: sans-serif; padding: 16px;">
                            <h2>ExpiryWatch Notification</h2>
                            <p>Your <strong>{row['document_type']}</strong> is set to expire on <strong>{row['expiry_date']}</strong> ({days_remaining} day(s) remaining).</p>
                            <p>Threshold triggered: {threshold}-day notice.</p>
                        </div>
                    """
                })
                updates_to_commit.append((column_flag, row["id"]))
                break # Send only the most immediate threshold breached in this run

    # Dispatch in chunks of 100 using Resend Batch API
    BATCH_SIZE = 100
    for i in range(0, len(batch_payload), BATCH_SIZE):
        chunk = batch_payload[i:i + BATCH_SIZE]
        try:
            resend.Batch.send(chunk)
        except Exception as e:
            print(f"[Scheduler] Error sending batch: {e}")

    # Mark flags in DB so duplicate alerts are never sent
    for col, doc_id in updates_to_commit:
        cursor.execute(f"UPDATE documents SET {col} = 1 WHERE id = ?", (doc_id,))
    
    conn.commit()
    conn.close()