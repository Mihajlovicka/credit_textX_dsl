import * as vscode from 'vscode';

import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
} from 'vscode-languageclient/node';

import { execFile } from 'child_process';

let client: LanguageClient;

export async function activate(context: vscode.ExtensionContext) {

    const pythonExtension = vscode.extensions.getExtension(
        'ms-python.python'
    );

    if (!pythonExtension) {
        vscode.window.showErrorMessage(
            'Bank Credit DSL requires the Microsoft Python extension.'
        );

        return;
    }

    const pythonApi = await pythonExtension.activate();

    const environmentPath =
        await pythonApi.environments.getActiveEnvironmentPath(
            vscode.window.activeTextEditor?.document.uri
        );

    const pythonPath = environmentPath?.path;

    if (!pythonPath) {
        vscode.window.showErrorMessage(
            'No Python interpreter is selected for Bank Credit DSL.'
        );

        return;
    }

    const serverOptions: ServerOptions = {
        command: pythonPath,

        args: [
            '-m',
            'bankdsl.language_server.server'
        ]
    };

    const clientOptions: LanguageClientOptions = {
        documentSelector: [
            {
                scheme: 'file',
                language: 'bankcredit'
            }
        ]
    };

    client = new LanguageClient(
        'bankcreditLanguageServer',
        'Bank Credit DSL Language Server',
        serverOptions,
        clientOptions
    );

    client.start();
}

export function deactivate(): Thenable<void> | undefined {

    if (!client) {
        return undefined;
    }

    return client.stop();
}