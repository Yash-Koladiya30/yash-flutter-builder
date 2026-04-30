# Screen Templates

Standard skeletons for the five most common screen types. Every new screen starts from one of these.

## List screen

```dart
class PostsScreen extends StatelessWidget {
  const PostsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Posts')),
      body: BlocBuilder<PostBloc, PostState>(
        builder: (context, state) {
          if (state is PostLoading) return const Center(child: CircularProgressIndicator());
          if (state is PostError) return _ErrorView(message: state.message);
          if (state is PostLoaded) {
            return ListView.builder(
              itemCount: state.posts.length,
              itemBuilder: (_, i) => PostCard(post: state.posts[i]),
            );
          }
          return const SizedBox.shrink();
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/posts/new'),
        child: const Icon(Icons.add),
      ),
    );
  }
}
```

## Detail screen

```dart
class PostDetailScreen extends StatelessWidget {
  final String id;
  const PostDetailScreen({super.key, required this.id});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Post')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Title', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          const Text('Body content...'),
        ],
      ),
    );
  }
}
```

## Form / edit screen

Use `Form` + `GlobalKey<FormState>` + `TextFormField` — see `form_handling.md`.

## Profile screen

Scaffold with header (avatar + name), stats row, then a list of setting tiles using `ListTile`.

## Auth screen

Single column, centered, `SafeArea` wrapper, `Form` with email + password, `FilledButton` submit.

## Rules

- Every screen ends in `Screen`.
- Every screen is a widget file under `lib/screens/`.
- Use `const` constructors wherever possible.
- Always wrap scrollable content in `ListView` / `CustomScrollView` — never a static `Column` that can overflow.
- Async data loading belongs in the BLoC, not in the widget's `initState`.
