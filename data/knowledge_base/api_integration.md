# API Integration

Use the `http` package for simple calls, `dio` when you need interceptors/cancellation. AppAspect default is `http`.

## Repository pattern

All network calls go through a Repository class. BLoCs never touch `http` directly.

```dart
class PostRepository {
  final http.Client _client;
  final String _baseUrl;

  PostRepository({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? 'https://api.example.com';

  Future<List<Post>> fetchPosts() async {
    final response = await _client.get(Uri.parse('$_baseUrl/posts'));
    if (response.statusCode != 200) {
      throw ApiException('Failed to load posts: ${response.statusCode}');
    }
    final List<dynamic> jsonList = json.decode(response.body) as List;
    return jsonList.map((j) => Post.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<Post> createPost({required String title, required String body}) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/posts'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'title': title, 'body': body}),
    );
    if (response.statusCode != 201) {
      throw ApiException('Failed to create post');
    }
    return Post.fromJson(json.decode(response.body) as Map<String, dynamic>);
  }
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => 'ApiException: $message';
}
```

## Typical BLoC integration

```dart
class PostBloc extends Bloc<PostEvent, PostState> {
  final PostRepository _repository;
  PostBloc(this._repository) : super(const PostInitial()) {
    on<LoadPosts>(_onLoadPosts);
  }

  Future<void> _onLoadPosts(LoadPosts event, Emitter<PostState> emit) async {
    emit(const PostLoading());
    try {
      final posts = await _repository.fetchPosts();
      emit(PostLoaded(posts));
    } on ApiException catch (e) {
      emit(PostError(e.message));
    } catch (e) {
      emit(PostError('Unexpected error: $e'));
    }
  }
}
```

## Rules

- Always check status codes — never assume 200.
- Wrap `json.decode` output in typed models (`Post.fromJson`), never expose `Map<String, dynamic>` to UI.
- Throw custom `ApiException`, catch it in BLoC, emit `*Error` state.
- Add a timeout: `.timeout(const Duration(seconds: 10))` on production calls.
- Never call APIs from widget `build()` methods.
