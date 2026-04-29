# main.dart — App Entry Point

Every Flutter app starts with `main.dart`. It wires up: Hive init (if used), BlocProviders, go_router, theme.

## Full template

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:my_app/blocs/auth_bloc.dart';
import 'package:my_app/blocs/post_bloc.dart';
import 'package:my_app/repositories/auth_repository.dart';
import 'package:my_app/repositories/post_repository.dart';
import 'package:my_app/router.dart';
import 'package:my_app/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();
  await Hive.openBox<Map>('posts');
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider(create: (_) => AuthRepository()),
        RepositoryProvider(create: (_) => PostRepository()),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider(create: (ctx) => AuthBloc(ctx.read<AuthRepository>())),
          BlocProvider(create: (ctx) => PostBloc(ctx.read<PostRepository>())),
        ],
        child: MaterialApp.router(
          title: 'My App',
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: ThemeMode.system,
          routerConfig: router,
          debugShowCheckedModeBanner: false,
        ),
      ),
    );
  }
}
```

## Rules

- `WidgetsFlutterBinding.ensureInitialized()` is required if `main` is async (Hive, shared_preferences, Firebase).
- Use `MaterialApp.router` (not `MaterialApp`) when using go_router.
- Always set `debugShowCheckedModeBanner: false` — cleaner screenshots.
- Put shared services (repositories) in `MultiRepositoryProvider` above `MultiBlocProvider`.
- Don't do heavy work in `build()` — it runs on every theme/locale change.
