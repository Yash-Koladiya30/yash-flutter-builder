# Navigation — go_router

AppAspect uses `go_router` for all navigation (not Navigator 1.0, not auto_route).

## Setup

```dart
final router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (ctx, st) => const HomeScreen()),
    GoRoute(path: '/details/:id',
      builder: (ctx, st) => DetailsScreen(id: st.pathParameters['id']!)),
  ],
);

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      routerConfig: router,
      title: 'My App',
    );
  }
}
```

## Rules

- All routes declared in a single `router` variable at app root.
- Use `context.go('/path')` for replacing, `context.push('/path')` for stacking.
- Never call `Navigator.push` directly — breaks the declarative model.
- Deep links work for free because go_router owns the URL.
