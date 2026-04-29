# Null Safety Rules (AppAspect)

Lessons from the v2.1.3 `NullPointerException` in `UserProfileScreen`.

## Rules

1. Never use `!` on a nullable that could be null at the point of access.
2. Prefer `?.` and `??` over `!`.
3. For late-initialized fields, use `late final` and assign in `initState`.
4. For async-loaded data, guard with a null check before access.

## Anti-pattern

```dart
Map<String, dynamic>? userData;

void _loadUserData() {
  final name = userData!['name']; // crashes if userData is null
}
```

## Correct pattern

```dart
Map<String, dynamic>? userData;

void _loadUserData() {
  final data = userData;
  if (data == null) return;
  final name = data['name'] ?? 'Unknown';
}
```

## Constructor discipline

- All required constructor params: use `required` with non-nullable types.
- Optional params: use nullable types or provide defaults, never both.
- `const` constructors wherever possible — enables widget reuse.
