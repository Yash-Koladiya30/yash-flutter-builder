# Async & Reactive Patterns in Flutter

Dart has `Future` (one-shot async) and `Stream` (continuous). Flutter has `FutureBuilder` / `StreamBuilder` to bind them to UI.

## Future + FutureBuilder

Use when you want to show a value once after an async operation.

```dart
FutureBuilder<List<Post>>(
  future: context.read<PostRepository>().fetchPosts(),
  builder: (context, snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Center(child: CircularProgressIndicator());
    }
    if (snapshot.hasError) {
      return ErrorView(message: 'Failed to load: ${snapshot.error}');
    }
    final posts = snapshot.data ?? [];
    return ListView.builder(
      itemCount: posts.length,
      itemBuilder: (_, i) => PostCard(post: posts[i]),
    );
  },
)
```

**Gotcha:** never create the future inside `build()` — it re-runs on every rebuild. Create it in `initState` of a StatefulWidget, or use BLoC.

## Stream + StreamBuilder

Use when values change over time (Firestore snapshots, WebSocket, timers).

```dart
StreamBuilder<User?>(
  stream: FirebaseAuth.instance.authStateChanges(),
  builder: (context, snapshot) {
    if (!snapshot.hasData) return const LoginScreen();
    return HomeScreen(user: snapshot.data!);
  },
)
```

## async/await basics

```dart
Future<void> _loadData() async {
  try {
    final posts = await _repository.fetchPosts();
    setState(() => _posts = posts);
  } catch (e) {
    setState(() => _error = 'Failed: $e');
  }
}
```

## Preferred approach — BLoC over FutureBuilder

For anything non-trivial, use a BLoC instead of `FutureBuilder`. Reasons:
- BLoC state survives widget rebuilds.
- Easier to test.
- Cleaner error states.

`FutureBuilder` is fine for quick one-off loads (like a splash screen fetching config).

## Rules

- Never `await` in `build()` — it runs thousands of times.
- Always handle `hasError` — network always fails eventually.
- Check `snapshot.connectionState` for loading state, not just `hasData`.
- Stream subscriptions in a `StatefulWidget` must be cancelled in `dispose()`.
