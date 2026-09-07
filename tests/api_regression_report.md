# API Regression Report

Passed: 7
Failed: 5

---

## clarify_property

Status: FAIL

### Failures
- Expected clarification=True

### SQL
```sql
SELECT 
    p.id,
    p.title,
    p.city,
    p.neighbourhood,
    p.price,
    p.bedrooms,
    p.bathrooms,
    p.size_sqm,
    p.property_type,
    p.distance_from_city_km,
    p.description
FROM 
    properties p
WHERE 
    p.intent = 'rent'
ORDER BY 
    p.price ASC, 
    p.size_sqm DESC
LIMIT 20
```

### Response
```text
20 properties found: renovated one-bedroom apartments in London, Rome, Paris, and other cities. Prices range from £810 to £844.
```

---

## clarify_affordable

Status: FAIL

### Failures
- Expected clarification=True

### SQL
```sql
SELECT 
    id,
    title,
    city,
    neighbourhood,
    intent,
    price,
    bedrooms,
    bathrooms,
    size_sqm,
    property_type,
    distance_from_city_km,
    description
FROM 
    properties
WHERE 
    intent = 'rent' AND 
    price <= 1000 AND 
    city IN ('London', 'Paris', 'Berlin', 'Amsterdam', 'Rome')
ORDER BY 
    price ASC
LIMIT 20
```

### Response
```text
Affordable one-bedroom apartments available in London, Rome, Paris, and other cities. Prices range from £810 to £844.
```

---

## city_switch

Status: FAIL

### Failures
- Missing response token: Berlin

### SQL
```sql

```

### Response
```text
Could you provide a few more details about what you're looking for?
```

---

## count_rome

Status: PASS

### SQL
```sql
SELECT COUNT(*) AS property_count
FROM properties
WHERE city = 'Rome' AND intent = 'rent' AND property_type = 'apartment'
```

### Response
```text
There are 18 apartments for rent in Rome matching your criteria.
```

---

## avg_price

Status: PASS

### SQL
```sql
SELECT AVG(price) AS avg_price
FROM properties
WHERE city = 'Rome' AND property_type = 'house'
```

### Response
```text
The average price for houses in Rome is €923,728.
```

---

## comparison

Status: PASS

### SQL
```sql
-- London
SELECT AVG(price) AS avg_price
FROM properties
WHERE city = 'London' AND intent = 'buy'
-- Berlin
SELECT AVG(price) AS avg_price
FROM properties
WHERE city = 'Berlin' AND intent = 'buy'
```

### Response
```text
London has the higher average price for properties for sale: £910,614, versus €878,555 in Berlin (London: £910,614, Berlin: €878,555).
```

---

## ranking_cheapest

Status: PASS

### SQL
```sql
SELECT id, title, city, neighbourhood, intent, price, bedrooms, bathrooms, size_sqm, property_type, distance_from_city_km
FROM properties
WHERE city = 'Berlin' AND property_type = 'apartment'
ORDER BY price ASC
LIMIT 5
```

### Response
```text
Here are the top 5 cheapest apartments in Berlin, ranked by price.
```

---

## ranking_closest

Status: FAIL

### Failures
- Missing SQL token: distance_from_city_km

### SQL
```sql

```

### Response
```text
How far from the city centre would you like to search? (e.g., 5km, 10km, 20km)
```

---

## radius

Status: FAIL

### Failures
- Forbidden SQL token: longitude
- Forbidden SQL token: latitude

### SQL
```sql
SELECT p.*
FROM properties p
JOIN city_centers cc ON ST_Distance(p.distance_from_city_km::geography, ST_SetSRID(ST_MakePoint(cc.longitude, cc.latitude), 4326)) <= 20000
WHERE p.city = 'Amsterdam' AND p.property_type = 'house'
LIMIT 20
```

### Response
```text
I wasn't able to complete that query after several attempts. Please try rephrasing — for example, specify a city, budget, or number of bedrooms. (Details: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) <class 'asyncpg.exceptions.UndefinedObjectError'>: type "geogr)
```

---

## title_pattern

Status: PASS

### SQL
```sql
SELECT *
FROM properties
WHERE title ILIKE '%modern%'
ORDER BY price ASC
LIMIT 20
```

### Response
```text
There are 20 properties with modern titles found across London, Berlin, Amsterdam, and other cities.
```

---

## description_pattern

Status: PASS

### SQL
```sql
SELECT *
FROM properties
WHERE intent = 'rent'
  AND description ILIKE '%attractive%'
ORDER BY price ASC, bedrooms DESC
LIMIT 20
```

### Response
```text
No properties matching your criteria were found.
```

---

## top_5

Status: PASS

### SQL
```sql
SELECT id, title, city, neighbourhood, intent, price, bedrooms, bathrooms, size_sqm, property_type, distance_from_city_km
FROM properties
ORDER BY price ASC
LIMIT 5
```

### Response
```text
Here are the top 5 cheapest properties, ranked by price.
```

---
