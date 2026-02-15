import sqlite3
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Cache objects
vectorizer = None
item_vectors = None
menu_items_cache = None


def build_model():
    global vectorizer, item_vectors, menu_items_cache

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM menu_items")
    menu_items = cur.fetchall()

    conn.close()

    if not menu_items:
        return

    menu_items_cache = menu_items

    item_texts = []

    for item in menu_items:
        text = f"{item['name']} {item['mood']} {item['sub_category_id']} "
        text += "veg " if item["is_veg"] else "nonveg "
        text += "glutenfree " if item["is_gluten_free"] else ""
        text += "nuts " if item["contains_nuts"] else ""
        text += "dairy " if item["contains_dairy"] else ""
        item_texts.append(text)

    vectorizer = TfidfVectorizer()
    item_vectors = vectorizer.fit_transform(item_texts)


def recommend(table_no, mood=None, no_dairy=False, no_nuts=False, veg_only=False):

    global vectorizer, item_vectors, menu_items_cache

    if vectorizer is None or item_vectors is None or menu_items_cache is None:
        build_model()

    if not menu_items_cache:
        return []

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------------------------
    # Current table orders
    # ---------------------------
    cur.execute("SELECT item_name FROM orders WHERE table_no = ?", (table_no,))
    ordered_items = [row["item_name"] for row in cur.fetchall()]

    # ---------------------------
    # Dietary Hard Filter (used everywhere)
    # ---------------------------
    dietary_mask = []
    for item in menu_items_cache:
        valid = 1
        if no_dairy and item["contains_dairy"]:
            valid = 0
        if no_nuts and item["contains_nuts"]:
            valid = 0
        if veg_only and not item["is_veg"]:
            valid = 0
        dietary_mask.append(valid)

    dietary_mask = np.array(dietary_mask)

    # ---------------------------
    # Popularity Boost (used in both cases)
    # ---------------------------
    cur.execute("""
        SELECT item_name, SUM(quantity) as total
        FROM orders
        GROUP BY item_name
    """)
    popularity_data = cur.fetchall()
    popularity_dict = {row["item_name"]: row["total"] for row in popularity_data}
    max_pop = max(popularity_dict.values()) if popularity_dict else 1

    popularity_scores = []
    for item in menu_items_cache:
        pop = popularity_dict.get(item["name"], 0)
        popularity_scores.append(pop / max_pop)

    popularity_scores = np.array(popularity_scores)

    # =====================================================
    # 🔥 AI COLD START (NO HISTORY) – VECTOR BASED
    # =====================================================
    if not ordered_items:

        user_query = ""

        if mood:
            user_query += mood + " "

        if veg_only:
            user_query += "veg "

        if no_dairy:
            user_query += "no dairy "

        if no_nuts:
            user_query += "no nuts "

        # Convert query to vector
        user_vector = vectorizer.transform([user_query])
        similarity_scores = cosine_similarity(user_vector, item_vectors)[0]

        final_scores = (
            0.70 * similarity_scores +
            0.30 * popularity_scores
        )

        final_scores = final_scores * dietary_mask

    else:

        # ---------------------------
        # 1️⃣ Collaborative Filtering
        # ---------------------------
        cur.execute("SELECT table_no, item_name FROM orders")
        all_orders = cur.fetchall()

        table_groups = {}
        for row in all_orders:
            table_groups.setdefault(row["table_no"], []).append(row["item_name"])

        collab_scores = []
        for item in menu_items_cache:
            score = 0
            for items in table_groups.values():
                intersection = len(set(items) & set(ordered_items))
                union = len(set(items) | set(ordered_items))
                jaccard = intersection / union if union > 0 else 0

                if item["name"] in items:
                    score += jaccard

            collab_scores.append(score)

        collab_scores = np.array(collab_scores)
        if collab_scores.max() > 0:
            collab_scores = collab_scores / collab_scores.max()

        # ---------------------------
        # 2️⃣ Content Similarity
        # ---------------------------
        user_text = " ".join(ordered_items)
        user_vector = vectorizer.transform([user_text])
        similarity_scores = cosine_similarity(user_vector, item_vectors)[0]

        # ---------------------------
        # 3️⃣ Mood Soft Boost (Not Overpowering)
        # ---------------------------
        mood_scores = []
        for item in menu_items_cache:
            score = 0
            if mood and item["mood"] and mood.lower() in item["mood"].lower():
                score = 1
            mood_scores.append(score)

        mood_scores = np.array(mood_scores)

        # ---------------------------
        # FINAL BALANCED HYBRID SCORE
        # ---------------------------
        final_scores = (
            0.30 * collab_scores +
            0.30 * similarity_scores +
            0.20 * popularity_scores +
            0.20 * mood_scores
        )

        final_scores = final_scores * dietary_mask

    # ---------------------------
    # Ranking
    # ---------------------------
    ranked_indices = np.argsort(final_scores)[::-1]

    recommendations = []
    used_categories = set()

    for idx in ranked_indices:
        item = menu_items_cache[idx]

        if dietary_mask[idx] == 0:
            continue

        if item["name"] in ordered_items:
            continue

        category = item["sub_category_id"]

        if category in used_categories and len(used_categories) < 5:
            continue

        used_categories.add(category)

        recommendations.append({
            "name": item["name"],
            "price": item["price"]
        })

        if len(recommendations) == 4:
            break

    conn.close()
    return recommendations