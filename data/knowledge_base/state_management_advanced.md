# State Management — Beyond the Basics

BLoC is the default. For small piece of ephemeral UI state, `StatefulWidget` is fine — don't over-architect.

## BlocProvider at app root

```dart
void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => AuthBloc(AuthRepository())),
        BlocProvider(create: (_) => PostBloc(PostRepository())),
      ],
      child: MaterialApp.router(
        routerConfig: router,
        theme: AppTheme.light,
      ),
    );
  }
}
```

## BlocBuilder vs BlocListener vs BlocConsumer

- `BlocBuilder` — rebuilds UI when state changes. Use for visual state.
- `BlocListener` — side effects (snackbar, navigation) when state changes. Does NOT rebuild.
- `BlocConsumer` — both at once.

```dart
BlocListener<AuthBloc, AuthState>(
  listener: (context, state) {
    if (state is AuthError) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(state.message)));
    } else if (state is AuthSuccess) {
      context.go('/home');
    }
  },
  child: LoginForm(),
)
```

## Equatable for state comparison

Without Equatable, BLoC re-emits identical states and UI rebuilds unnecessarily.

```dart
class PostLoaded extends PostState {
  final List<Post> posts;
  const PostLoaded(this.posts);
  @override
  List<Object?> get props => [posts];
}
```

## context.read vs context.watch

- `context.read<Bloc>()` — one-time access, doesn't rebuild. Use in event handlers.
- `context.watch<Bloc>()` — subscribes, rebuilds on every state change. Use in `build()`.
- `BlocBuilder` is usually better than `context.watch` — it's explicit about rebuild scope.

## When NOT to use BLoC

- Single toggle button's pressed state → `StatefulWidget`.
- Controller for a `TextField` → `TextEditingController`, no BLoC.
- `AnimationController` → directly in state, no BLoC.

## Rules

- One BLoC per feature, not per widget.
- States and events must be `Equatable`.
- Never call `bloc.add()` from inside `build()` — put it in `initState`, a callback, or a BlocListener.
