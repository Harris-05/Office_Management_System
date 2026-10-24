// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import PublicForm from './PublicForm';
import { api } from '../api';

vi.mock('../api', async importOriginal => ({ ...await importOriginal<typeof import('../api')>(), api: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function fill() {
 const user = userEvent.setup();
 await user.type(screen.getByLabelText('Your name'), 'Test Visitor');
 await user.type(screen.getByLabelText('Email address'), 'visitor@example.test');
 await user.type(screen.getByLabelText('Subject'), 'A local question');
 await user.type(screen.getByLabelText('Message'), 'I would like to find out more about the local team.');
 await user.click(screen.getByRole('checkbox'));
 return user;
}

test('invalid fields are explained and focused without sending a request', async () => {
 render(<PublicForm kind="contact" language="en" branches={[]} />);
 await userEvent.click(screen.getByRole('button', {name:'Send message'}));
 expect(api).not.toHaveBeenCalled();
 expect(screen.getByLabelText('Your name')).toHaveFocus();
 expect(screen.getByRole('alert')).toHaveTextContent('Check the highlighted fields');
});

test('submit locks duplicate requests and exposes a persistent receipt on success', async () => {
 let resolve!: (value: unknown) => void;
 vi.mocked(api).mockImplementation(() => new Promise(done => {resolve = done;}) as ReturnType<typeof api>);
 render(<PublicForm kind="contact" language="en" branches={[]} />);
 const user = await fill();
 await user.dblClick(screen.getByRole('button', {name:'Send message'}));
 expect(api).toHaveBeenCalledTimes(1);
 expect(screen.getByRole('button', {name:'Sending…'})).toBeDisabled();
 await act(async () => resolve({id:'receipt-123'}));
 expect(screen.getByRole('status')).toHaveTextContent('Message received');
 expect(screen.getByRole('status')).toHaveTextContent('receipt-123');
});

test('a network failure keeps the message and reuses its request reference on retry', async () => {
 vi.mocked(api).mockRejectedValueOnce(new Error('offline')).mockResolvedValue({id:'saved'});
 render(<PublicForm kind="contact" language="en" branches={[]} />);
 const user = await fill();
 await user.click(screen.getByRole('button', {name:'Send message'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('try again');
 expect(screen.getByLabelText('Message')).toHaveValue('I would like to find out more about the local team.');
 await user.click(screen.getByRole('button', {name:'Send message'}));
 expect(vi.mocked(api).mock.calls[0][2]).toEqual(vi.mocked(api).mock.calls[1][2]);
 expect(await screen.findByRole('status')).toHaveTextContent('Message received');
});
