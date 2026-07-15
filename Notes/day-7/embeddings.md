## How Embeddings Work

### Step 1: Text → Vector

```python
# Using embedding model
text = "How to fix database errors?"
embedding = model.encode(text)

# Result: array of 1536 numbers
embedding = [0.23, -0.45, 0.78, ..., 0.12]

```

### Step 2: Compare Vectors

```python
# Two similar texts
text1 = "database error"
text2 = "SQL connection failed"

vector1 = [0.8, 0.6, 0.1, ...]
vector2 = [0.7, 0.5, 0.2, ...]

# Calculate similarity (cosine similarity)
similarity = compare(vector1, vector2)
# Result: 0.92 (very similar!)

```

### Step 3: Search

```python
# User query
query = "Why is my database slow?"
query_vector = model.encode(query)

# Find similar documents
results = vector_db.search(query_vector, top_k=5)

# Returns:
# 1. "Database performance tuning" (similarity: 0.89)
# 2. "Slow query optimization" (similarity: 0.85)
# 3. "Index best practices" (similarity: 0.78)

```