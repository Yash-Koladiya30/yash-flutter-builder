# Dart 3 Language Essentials for Flutter

Flutter apps are written in Dart 3. These are the features the code generator must get right.

## Null safety (non-negotiable)

Every type is non-nullable by default. Append `?` to make it nullable.

```dart
String name;         // non-nullable — must be initialized
String? maybeName;   // nullable — can be null
late String lazy;    // deferred init — assigned before first read
```

Access nullable safely:

```dart
name.length          // OK if non-nullable
maybeName?.length    // null-safe call, returns null if maybeName is null
maybeName!.length    // force unwrap — CRASHES if null; avoid
maybeName ?? 'N/A'   // null-coalescing — 'N/A' if null
```

## Records (Dart 3)

```dart
(String, int) user = ('Alice', 30);
print(user.$1);    // 'Alice'
print(user.$2);    // 30

// Named records — cleaner
({String name, int age}) u = (name: 'Alice', age: 30);
print(u.name);
```

## Pattern matching

```dart
switch (state) {
  case PostLoading():   return const CircularProgressIndicator();
  case PostError(:final message):   return Text(message);
  case PostLoaded(:final posts):   return PostList(posts: posts);
}
```

## Sealed classes for BLoC states

```dart
sealed class PostState extends Equatable {
  const PostState();
  @override List<Object?> get props => [];
}

class PostInitial extends PostState {}
class PostLoading extends PostState {}
class PostLoaded extends PostState {
  final List<Post> posts;
  const PostLoaded(this.posts);
  @override List<Object?> get props => [posts];
}
class PostError extends PostState {
  final String message;
  const PostError(this.message);
  @override List<Object?> get props => [message];
}
```

## Async/await

All asynchronous Flutter code uses `async`/`await`. Marked functions return a `Future<T>`.

```dart
Future<List<Post>> fetchPosts() async {
  final response = await _client.get(uri);
  return parse(response.body);
}
```

## Rules

- Always annotate types on public APIs — `var` is fine locally but not for return types.
- Prefer `final` over `var` for immutability — compiler catches mutations.
- Use `const` constructors everywhere possible — enables widget reuse.
- Avoid `late` unless you have no choice — it defers the null-safety check to runtime.
