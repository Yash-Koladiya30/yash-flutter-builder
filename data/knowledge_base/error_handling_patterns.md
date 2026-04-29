# Error Handling Patterns

Users never see a raw stack trace. Every error path has a typed exception, a BLoC state, and a human-readable UI response.

## Layered approach

1. **Repository** throws typed exceptions (`ApiException`, `NotFoundException`, `NetworkException`).
2. **BLoC** catches them and emits `*Error` states.
3. **Widget** renders the error state with a friendly message + retry button.

## Repository layer

```dart
try {
  final response = await _client.get(uri).timeout(const Duration(seconds: 10));
  if (response.statusCode == 404) throw NotFoundException();
  if (response.statusCode >= 500) throw ServerException();
  if (response.statusCode != 200) throw ApiException('HTTP ${response.statusCode}');
  return parseResponse(response);
} on SocketException {
  throw NetworkException('No internet connection');
} on TimeoutException {
  throw NetworkException('Request timed out');
}
```

## BLoC layer

```dart
Future<void> _onLoadPosts(LoadPosts _, Emitter<PostState> emit) async {
  emit(const PostLoading());
  try {
    final posts = await _repository.fetchPosts();
    emit(PostLoaded(posts));
  } on NetworkException catch (e) {
    emit(PostError(message: e.message, isRetryable: true));
  } on NotFoundException {
    emit(const PostError(message: 'No posts found', isRetryable: false));
  } catch (e) {
    emit(PostError(message: 'Something went wrong', isRetryable: true));
  }
}
```

## UI layer — reusable error widget

```dart
class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const ErrorView({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.error_outline, size: 56, color: Theme.of(context).colorScheme.error),
          const SizedBox(height: 16),
          Text(message, style: Theme.of(context).textTheme.bodyLarge),
          if (onRetry != null) ...[
            const SizedBox(height: 16),
            FilledButton(onPressed: onRetry, child: const Text('Try again')),
          ],
        ],
      ),
    );
  }
}
```

## Rules

- Never show raw exception text (`e.toString()`) to users.
- Always include a retry action for network errors.
- Use `SnackBar` for transient errors (action failed but state is fine).
- Use full-screen error view when there's nothing to show underneath.
